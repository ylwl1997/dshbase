/*
 * xdma_minimal.c - Minimal Xilinx XDMA driver (K72专用, 支持多卡)
 * 目标板: K72 Kintex-7 xc7k410t ffg900
 * PCI ID : 10EE:7028
 * 内核   : Kylin V10 aarch64 Linux 4.19.90
 *
 * 关键修复 (K72专属补丁):
 *  ① 固定次设备号替代 MISC_DYNAMIC_MINOR
 *  ② ARM64 PCIe MMIO 映射改用 pgprot_noncached + VM_IO/VM_PFNMAP
 *
 * 设备节点 (每卡一组, idx=0,1,...):
 *   /dev/xdma{idx}_user  open+mmap → BAR0
 *   /dev/xdma{idx}_h2c_0 pwrite    → BAR1优先
 *   /dev/xdma{idx}_c2h_0 pread     → BAR2优先
 */
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/io.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/mm.h>
#include <linux/uaccess.h>
#include <linux/dma-mapping.h>
#include <linux/slab.h>
#include <linux/mutex.h>

#define MAX_BAR   6
#define MAX_DEVS  4
#define NAME_SZ   32

/* 每卡占用 3 个固定次设备号: user/h2c/c2h */
#define XDMA_MINOR_BASE  160
#define XDMA_MINOR_STRIDE 3

struct xdma_dev {
    struct pci_dev *pdev;
    int             idx;
    void __iomem   *bar[MAX_BAR];
    resource_size_t bar_start[MAX_BAR];
    resource_size_t bar_len[MAX_BAR];
    int             bar_valid[MAX_BAR];

    struct miscdevice user_misc;
    char              user_name[NAME_SZ];
    struct miscdevice h2c_misc;
    char              h2c_name[NAME_SZ];
    int               h2c_bar;
    int               h2c_reg;
    struct miscdevice c2h_misc;
    char              c2h_name[NAME_SZ];
    int               c2h_bar;
    int               c2h_reg;
};

static struct xdma_dev *g_devs[MAX_DEVS];
static DEFINE_MUTEX(g_lock);

static int alloc_idx(void)
{
    int i;
    for (i = 0; i < MAX_DEVS; i++)
        if (!g_devs[i])
            return i;
    return -1;
}

static int xdma_user_open(struct inode *inode, struct file *filp)
{
    struct miscdevice *misc = filp->private_data;
    struct xdma_dev *dev = container_of(misc, struct xdma_dev, user_misc);
    filp->private_data = dev;
    return 0;
}
static int xdma_user_release(struct inode *inode, struct file *filp) { return 0; }

static int xdma_user_mmap(struct file *filp, struct vm_area_struct *vma)
{
    struct xdma_dev *dev = filp->private_data;
    unsigned long size, pfn, off;
    int ret;

    if (!dev || !dev->bar_valid[0]) return -ENODEV;

    off  = (unsigned long)vma->vm_pgoff << PAGE_SHIFT;
    if (off >= dev->bar_len[0]) return -EINVAL;
    size = vma->vm_end - vma->vm_start;
    if (size > dev->bar_len[0] - off)
        size = dev->bar_len[0] - off;

    vma->vm_flags   |= VM_IO | VM_PFNMAP | VM_DONTEXPAND | VM_DONTDUMP;
    vma->vm_page_prot = pgprot_noncached(vma->vm_page_prot);

    pfn = (dev->bar_start[0] + off) >> PAGE_SHIFT;
    ret = remap_pfn_range(vma, vma->vm_start, pfn, size, vma->vm_page_prot);
    if (ret)
        pr_err("xdma%d: mmap BAR0 off=%lx sz=%lx ret=%d\n",
               dev->idx, off, size, ret);
    return ret;
}

static const struct file_operations xdma_user_fops = {
    .owner   = THIS_MODULE,
    .open    = xdma_user_open,
    .release = xdma_user_release,
    .mmap    = xdma_user_mmap,
};

static ssize_t xdma_h2c_write(struct file *filp, const char __user *buf,
                              size_t cnt, loff_t *ppos)
{
    struct xdma_dev *dev = filp->private_data;
    int bar;
    void __iomem *base;
    ssize_t ret = 0;
    u32 val;
    size_t i;

    if (!dev) return -ENODEV;
    bar = (dev->h2c_bar >= 0) ? dev->h2c_bar : 0;
    if (bar < 0 || bar >= MAX_BAR || !dev->bar_valid[bar]) return -ENODEV;
    base = dev->bar[bar];

    for (i = 0; (i + 4) <= cnt && (*ppos + i + 4) <= dev->bar_len[bar]; i += 4) {
        if (copy_from_user(&val, buf + i, 4)) return -EFAULT;
        writel(val, base + *ppos + i);
        ret += 4;
    }
    *ppos += ret;
    return ret ? ret : (cnt ? -EINVAL : 0);
}
static int xdma_h2c_open(struct inode *inode, struct file *filp)
{
    struct miscdevice *misc = filp->private_data;
    struct xdma_dev *dev = container_of(misc, struct xdma_dev, h2c_misc);
    filp->private_data = dev;
    return 0;
}
static const struct file_operations xdma_h2c_fops = {
    .owner   = THIS_MODULE,
    .open    = xdma_h2c_open,
    .write   = xdma_h2c_write,
};

static ssize_t xdma_c2h_read(struct file *filp, char __user *buf,
                             size_t cnt, loff_t *ppos)
{
    struct xdma_dev *dev = filp->private_data;
    int bar;
    void __iomem *base;
    ssize_t ret = 0;
    u32 val;
    size_t i;

    if (!dev) return -ENODEV;
    bar = (dev->c2h_bar >= 0) ? dev->c2h_bar : 0;
    if (bar < 0 || bar >= MAX_BAR || !dev->bar_valid[bar]) return -ENODEV;
    base = dev->bar[bar];

    for (i = 0; (i + 4) <= cnt && (*ppos + i + 4) <= dev->bar_len[bar]; i += 4) {
        val = readl(base + *ppos + i);
        if (copy_to_user(buf + i, &val, 4)) return -EFAULT;
        ret += 4;
    }
    *ppos += ret;
    return ret ? ret : (cnt ? -EINVAL : 0);
}
static int xdma_c2h_open(struct inode *inode, struct file *filp)
{
    struct miscdevice *misc = filp->private_data;
    struct xdma_dev *dev = container_of(misc, struct xdma_dev, c2h_misc);
    filp->private_data = dev;
    return 0;
}
static const struct file_operations xdma_c2h_fops = {
    .owner   = THIS_MODULE,
    .open    = xdma_c2h_open,
    .read    = xdma_c2h_read,
};

static const struct pci_device_id xdma_ids[] = {
    { PCI_DEVICE(0x10EE, 0x7028) },
    { PCI_DEVICE(0x10EE, 0x7021) },
    { PCI_DEVICE(0x10EE, 0x7027) },
    { 0, }
};
MODULE_DEVICE_TABLE(pci, xdma_ids);

static int xdma_probe(struct pci_dev *pdev, const struct pci_device_id *id)
{
    struct xdma_dev *dev;
    int ret, i, idx;
    int h2c_bar = -1, c2h_bar = -1;
    resource_size_t end_tmp;

    mutex_lock(&g_lock);
    idx = alloc_idx();
    if (idx < 0) {
        mutex_unlock(&g_lock);
        dev_err(&pdev->dev, "too many K72 devices (max %d)\n", MAX_DEVS);
        return -ENOMEM;
    }

    dev = devm_kzalloc(&pdev->dev, sizeof(*dev), GFP_KERNEL);
    if (!dev) {
        mutex_unlock(&g_lock);
        return -ENOMEM;
    }
    dev->pdev = pdev;
    dev->idx = idx;
    g_devs[idx] = dev;
    mutex_unlock(&g_lock);

    ret = pci_enable_device_mem(pdev);
    if (ret) {
        dev_err(&pdev->dev, "pci_enable_device_mem failed %d\n", ret);
        goto err_slot;
    }
    pci_set_master(pdev);
    dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(64));

    for (i = 0; i < MAX_BAR; i++) {
        resource_size_t start = pci_resource_start(pdev, i);
        resource_size_t len   = pci_resource_len(pdev, i);
        if (!start || !len) { dev->bar_valid[i] = 0; continue; }
        dev->bar_start[i] = start;
        dev->bar_len[i]   = len;
        dev->bar[i] = pci_iomap_range(pdev, i, 0, len);
        if (!dev->bar[i])
            dev->bar[i] = devm_ioremap(&pdev->dev, start, len);
        if (dev->bar[i]) {
            dev->bar_valid[i] = 1;
            end_tmp = start + len - 1;
            dev_info(&pdev->dev, "xdma%d BAR%d: %pa-%pa (%pa bytes)\n",
                     idx, i, &start, &end_tmp, &len);
        } else {
            dev->bar_valid[i] = 0;
            dev_err(&pdev->dev, "BAR%d mapping failed\n", i);
        }
    }

    if (dev->bar_valid[1] && dev->bar_len[1] >= 0x10000)
        h2c_bar = 1;
    else
        for (i = 2; i < MAX_BAR; i++)
            if (dev->bar_valid[i] && dev->bar_len[i] >= 0x10000) {
                h2c_bar = i; break;
            }

    if (dev->bar_valid[2] && dev->bar_len[2] >= 0x10000 && 2 != h2c_bar)
        c2h_bar = 2;
    else
        for (i = 2; i < MAX_BAR; i++)
            if (dev->bar_valid[i] && dev->bar_len[i] >= 0x10000 && i != h2c_bar) {
                c2h_bar = i; break;
            }

    dev->h2c_bar = h2c_bar;
    dev->c2h_bar = c2h_bar;

    snprintf(dev->user_name, NAME_SZ, "xdma%d_user", idx);
    dev->user_misc.minor  = XDMA_MINOR_BASE + idx * XDMA_MINOR_STRIDE;
    dev->user_misc.name   = dev->user_name;
    dev->user_misc.fops   = &xdma_user_fops;
    dev->user_misc.parent = &pdev->dev;
    ret = misc_register(&dev->user_misc);
    if (ret) {
        dev_err(&pdev->dev, "user misc_register failed: %d\n", ret);
        goto err_disable;
    }
    dev_info(&pdev->dev, "Created /dev/%s (minor=%d)\n",
             dev->user_name, (int)dev->user_misc.minor);

    if (h2c_bar >= 0) {
        snprintf(dev->h2c_name, NAME_SZ, "xdma%d_h2c_0", idx);
        dev->h2c_misc.minor  = XDMA_MINOR_BASE + idx * XDMA_MINOR_STRIDE + 1;
        dev->h2c_misc.name   = dev->h2c_name;
        dev->h2c_misc.fops   = &xdma_h2c_fops;
        dev->h2c_misc.parent = &pdev->dev;
        ret = misc_register(&dev->h2c_misc);
        if (ret) {
            dev_warn(&pdev->dev, "h2c misc_register failed: %d\n", ret);
            dev->h2c_reg = 0;
        } else {
            dev->h2c_reg = 1;
            dev_info(&pdev->dev, "Created /dev/%s (BAR%d)\n",
                     dev->h2c_name, h2c_bar);
        }
    }

    if (c2h_bar >= 0) {
        snprintf(dev->c2h_name, NAME_SZ, "xdma%d_c2h_0", idx);
        dev->c2h_misc.minor  = XDMA_MINOR_BASE + idx * XDMA_MINOR_STRIDE + 2;
        dev->c2h_misc.name   = dev->c2h_name;
        dev->c2h_misc.fops   = &xdma_c2h_fops;
        dev->c2h_misc.parent = &pdev->dev;
        ret = misc_register(&dev->c2h_misc);
        if (ret) {
            dev_warn(&pdev->dev, "c2h misc_register failed: %d\n", ret);
            dev->c2h_reg = 0;
        } else {
            dev->c2h_reg = 1;
            dev_info(&pdev->dev, "Created /dev/%s (BAR%d)\n",
                     dev->c2h_name, c2h_bar);
        }
    }

    pci_set_drvdata(pdev, dev);
    return 0;

err_disable:
    pci_disable_device(pdev);
err_slot:
    mutex_lock(&g_lock);
    g_devs[idx] = NULL;
    mutex_unlock(&g_lock);
    return ret;
}

static void xdma_remove(struct pci_dev *pdev)
{
    struct xdma_dev *dev = pci_get_drvdata(pdev);
    int i, idx;
    if (!dev) return;
    idx = dev->idx;

    if (dev->c2h_reg) misc_deregister(&dev->c2h_misc);
    if (dev->h2c_reg) misc_deregister(&dev->h2c_misc);
    misc_deregister(&dev->user_misc);

    for (i = 0; i < MAX_BAR; i++)
        if (dev->bar_valid[i] && dev->bar[i])
            pci_iounmap(pdev, dev->bar[i]);
    pci_disable_device(pdev);

    mutex_lock(&g_lock);
    g_devs[idx] = NULL;
    mutex_unlock(&g_lock);
    dev_info(&pdev->dev, "xdma%d removed\n", idx);
}

static struct pci_driver xdma_driver = {
    .name     = "xdma",
    .id_table = xdma_ids,
    .probe    = xdma_probe,
    .remove   = xdma_remove,
};
module_pci_driver(xdma_driver);

MODULE_DESCRIPTION("K72 Xilinx XDMA minimal driver (multi-card, ARM64 stable)");
MODULE_LICENSE("GPL");
MODULE_AUTHOR("K72 Team");
