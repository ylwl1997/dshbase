/*
 * Serdes.c
 *
 *  Created on: 2022-9-7
 *      Author: Administrator
 */
#include "JLK1263.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/*Local software delay function*/
static void PLLDelay(int Count)
{
	 Uint32 i = Count;
	 while(i--){
	     asm(" NOP 1");
	 }
}

//硬件复位
void reset_1263()
{
//	AddressRST = 0xAA55;   //释放复位,拉高
//	PLLDelay(100000);
//	AddressRST = 0x55AA;   //复位,拉低
//	PLLDelay(100000);
//	AddressRST = 0xAA55;   //释放复位，拉高
	Smart_Reg(0x4000) = 0x1;
	PLLDelay(100000);
	Smart_Reg(0x0004) = 0x0;
	PLLDelay(100000);
	Smart_Reg(0x0004) = 0x1;
}

void reset_fpga_fifo()
{
	Smart_Reg(0x5000) = 0x1;
	PLLDelay(100000);
}

//检测A或者B通道
bool check_chanel_status(char chanel)
{
	volatile Uint16 temp = 0;

	if(chanel == 'A')
	{
		temp = REG(0xA);               //A->7,A通道状态寄存器
		while(1){
			if((temp & 0x03) == 0x3)   //A通道处于活动且空闲状态
				return true;
			temp = REG(0xA);
		}
	}
	else if(chanel == 'B')
	{
		temp = REG(0xB);               //b->7,B通道状态寄存器
		while(1){
			if((temp & 0x03) == 0x3)   //B通道处于活动且空闲状态
				return true;
			temp = REG(0xB);
		}
	}
	return false;
}

/*获取A或者B通道状态*/
bool get_chanel_status(char chanel)
{
	volatile Uint16 temp = 0;

	if(chanel == 'A')
	{
		temp = (REG(0xA) & 0x03);
		if(temp != 0x3)   //A通道处于活动且空闲状态
		{
			return false;
		}
	}
	else if(chanel == 'B')
	{
		temp = (REG(0xB) & 0x03);
		if(temp != 0x3)   //A通道处于活动且空闲状态
		{
			return false;
		}
	}

	return true;
}

void configNC_Memory_Map(Uint32 stack_address,Uint32 memory_address,Uint16 exch_count)
{
	MEM(0x102) =  stack_address;                //设置栈指针A
	MEM(0x103) =  0xffff - exch_count;           //交换个数

	MEM(stack_address + 0x4) = 0;
	MEM(stack_address + 0x6) = memory_address & 0xffff;
	MEM(stack_address + 0x7) = (memory_address>>16) & 0xffff;
}

//交换组使能测试，测试使用
void configNC_Memory_Map_Group(Uint32 stack_address,Uint16 EXCH_Gap_Time/*us*/,Uint32 memory_address,Uint16 exch_count)
{
	Uint16 i = 0;

	MEM(0x102) =  stack_address;                //设置栈指针A
	MEM(0x103) =  0xffff - exch_count;           //交换个数

	for(i=0;i<exch_count;i++)
	{
		MEM(stack_address + 0x4 + 8*i) = EXCH_Gap_Time;
		MEM(stack_address + 0x6 + 8*i) = memory_address & 0xffff;
		MEM(stack_address + 0x7 + 8*i) = (memory_address>>16) & 0xffff;
	}
}

void startctrlxmit(bool soft_reset,bool ctrlnc1_send,bool ctrlnc2_send)
{
	REG(0x1) = soft_reset | (ctrlnc1_send<<4) | (ctrlnc2_send<<7);
}

void ctrlnc_SendData(Uint32 memory_address,Uint16 *Data,Uint16 Byte_Count)
{
	Uint16 i = 0;

    for(i=0;i<Byte_Count/2;i++)
    	MEM(memory_address+0x8+i) = Data[i];
}

Uint16 get_exchangeblock_status(Uint32 stack_address)
{
    return MEM(stack_address);
}

void ConfigctrlNC_TargetNT(Uint16 memory_address,Uint16 NT1_ID,Uint16 NT2_ID,Uint16 NT3_ID,Uint16 NT4_ID,Uint16 subaddress,\
        bool TR,bool mode,bool state,bool INT,bool retry_en,bool prior,bool one_chanel,bool CH_B,Uint16 NT_num, \
        Uint16 NT1_type,Uint16 NT2_type,Uint16 NT3_type,Uint16 NT4_type,Uint16 Byte_Count)
{
	MEM(memory_address)       = NT1_ID;
	MEM(memory_address + 0x1) = NT2_ID;
	MEM(memory_address + 0x2) = NT3_ID;
	MEM(memory_address + 0x3) = NT4_ID;

	MEM(memory_address + 0x4) = subaddress;
	MEM(memory_address + 0x5) = Byte_Count;
	MEM(memory_address + 0x6) = TR | (mode<<1) | (state<<2) |  (INT<<3) | (retry_en<<4) | (prior<<5) | (one_chanel<<6) | (CH_B<<7) | (NT_num<<8);
	MEM(memory_address + 0x7) = NT1_type | (NT2_type<<4) | (NT3_type<<8) | (NT4_type<<12);
}

//获取控制流状态字
bool getCtrlNcStatusWord(Uint16 stack_address)
{
	volatile Uint16 temp = 0;
	char count = 10;

	while(count--){
	    temp = MEM(stack_address);
		if((temp & 0x8000) == 0x8000)    //控制流NC块状态字 ，传输完毕后EOE置1
		   return true;
	}
	return false;    //0x8002，B通道响应状态寄存器
}
//获取中断状态
Uint16 getInteruptStatus()
{
	return REG(0x6);
}

void MemorySpaceInit()
{
	Uint32 i = 0;
	/*节点存储区域初始化*/
	for(i=0;i<0x10000;i++)
	{
		MEM(i) = 0;
	}
	/*ctrlNC超时配置初始化*/
	for(i=0;i<0x100;i++)
	{
		MEM(i) = 0xFFFF;
	}

}

//设置节点ID
void configID(Uint16 ID)
{
	REG(0x0) = ID;
}

//通道使能
void configchanelEnable(Uint16 enable)
{
	REG(0x3) = enable;     //设置节点ID
}

//配置中断模式
void configInteruptMode(Uint16 InteruptMode)
{
	REG(0x4) = InteruptMode;   //配置脉冲中断，自动清除
}

//配置中断模式
void configInteruptMask(Uint16 InteruptMask)
{
	REG(0x5) = InteruptMask;   //使能控制流NT交换结束中断
}

//配置时间戳
/*
 * 0:   32us
 * 1:   16us
 * 2:   8us
 * 3:   4us
 * 4:   2us
 * 5:   1us
 */
void configtimestamp(Uint16 timestamp)
{
	REG(0x7) = timestamp;
}

/*
 * 配置ctrlNT
 */
void configctrlNT(Uint16 reg1,Uint16 reg2)
{
	REG(0x24) = reg1;  //设置控制流NT寄存器1
	REG(0x25) = reg2;  //设置控制流NT寄存器2
}

/*
 * 第 1 路 SmartNC 超时设置
 */
void config_smartNC1_timeout(Uint16 time_out)
{
	REG(0x29) = time_out;
}

/*
 * 第 1 路 SmartNC 配置
 */
void config_smartNC1(Uint16 reg)
{
	REG(0x2a) = reg;
}

/*
 * smartncchanel:对应的nc通道
 * smartncID : 终端ID
 * smartntchanel:1 - 4
 * long_short_mode:1,短报文；0：长报文
 */
void configsmartNTchanel(Uint16 smartntchanel,Uint16 smartncID,Uint16 smartncchanel,Uint16 long_short_mode)
{
	switch(smartntchanel){
		case 1:
			REG(0x3c) = smartncID | (smartncchanel<<12) | (long_short_mode<<14);
			break;
		case 2:
			REG(0x3d) = smartncID | (smartncchanel<<12) | (long_short_mode<<14);
			break;
		case 3:
			REG(0x3e) = smartncID | (smartncchanel<<12) | (long_short_mode<<14);
			break;
		case 4:
			REG(0x3f) = smartncID | (smartncchanel<<12) | (long_short_mode<<14);
			break;
	}
}

/*
 * chanel:   配置第几路
 * NC_type:  000-第 1 路 CTRLNC;
 *           001- 第 2 路 CTRLNC;
 *           010-第 1 路 SMARTNC;
 *           011-第 2 路 SMARTNC;
 *           100-第 3 路 SMARTNC;
 *           101- 第 4 路 SMARTNC;
 * ctrlNC_ID: 与第几路通道配对的ctrlNC ID
 */
void configctrlNTchanel(Uint16 chanel,Uint16 NC_type,Uint16 ctrlNC_ID)
{
	MEM(0x120 + chanel -1) = ctrlNC_ID| 0x8000 | (NC_type<<12);
}

//初始化未使用的ctrlNT通道
void InitUnusedctrlNTchanel(Uint16 unused_begin_chanel)
{
	Uint16 i = 0;
	//剩余15路不使能
	for(i=unused_begin_chanel;i<15;i++)
	{
		MEM(0x120+i) = 0;
	}
}

/*配置ctrlnt接收地址*/
void config_recv_ctrlnt_memory(Uint16 chanel,Uint16 area,Uint16 service,Uint16 contrl_word, Uint16 subaddress,Uint32 recv_address)
{
	MEM(0x200*chanel)                     = area;
	MEM(0x200*chanel + 0x1)               = service;
	MEM(0x200*chanel + 0x40 + subaddress) = contrl_word;
	MEM(0x200*chanel + 0x82 + subaddress*2 - 2) = recv_address & 0xffff;    	   //低地址
	MEM(0x200*chanel + 0x83 + subaddress*2 - 2) = (recv_address>>16) & 0xffff;	   //高地址
}

/*配置ctrlnt发送地址*/
void config_send_ctrlnt_memory(Uint16 chanel,Uint16 subaddress,Uint32 send_address)
{
	MEM(0x200*chanel + 0xc0 + subaddress*2) = send_address & 0xffff;     //低地址
	MEM(0x200*chanel + 0xc1 + subaddress*2) = (send_address>>16) & 0xffff;		     //高地址
}

//工作模式配置
void config_workmode(bool ctrlNC1,bool ctrlNC2,bool ctrlNT,bool smartnc1,bool smartnc2,bool smartnc3,bool smartnc4,bool smartnt1,bool smartnt2,\
		bool smartnt3,bool smartnt4,bool monitor)
{
	REG(0x2) = ctrlNC1 | (ctrlNT<<1) | (smartnc1<<4) | (smartnc2<<5) | (smartnc3<<6) |(smartnc4<<7) | (smartnt1<<8) \
			| (smartnt2<<9) | (smartnt3 <<10) | (smartnt4 <<11) | (ctrlNC2 <<12) | (monitor<<13);	//ctrlNT,smartNT1、smartNT2使能
}

//配置第1路控制流NC寄存器1
void config_ctrlnc1_retry(Uint16 retry,Uint16 retry_num)
{
	REG(0x18) = (retry<<10) | (retry_num<<15) | (1<<6);
	REG(0x19) = 0;
}

//配置第1路控制流NC寄存器1，使能交换间隔
void config_ctrlnc1_retry_group(Uint16 retry,Uint16 retry_num,Uint16 gap_enable)
{
	REG(0x18) = (retry<<10) | (retry_num<<15) | (1<<6) | (gap_enable<<8);
	REG(0x19) = 0;
}

//配置NT接收栈地址
void configNTSP(Uint16 stack_address)
{
	MEM(GLINK_NT_SP) = stack_address;
}

//返回发送端NC ID
Uint16 get_current_Target_NC_ID(Uint16* NC_ID,Uint16* TR,Uint16* subaddress,Uint16* bytes_len,Uint32* Data_Block_Address)
{
    static Uint16 count = 0;
    Uint16 current_sp   = 0;
    Uint16 Low_address,High_address;

    count++;
    printf("sp = 0x%x\n",MEM(GLINK_NT_SP));
    if(count >= 512)
    {
        count -= 512;
        current_sp = MEM(GLINK_NT_SP) + 8*64 - 8*sizeof(Uint16);
    }
    else {
        current_sp = MEM(GLINK_NT_SP)  - 8*sizeof(Uint16);
    }

	*NC_ID              = (MEM(current_sp + 1) & 0xfff);
	*TR                 = (MEM(current_sp + 4) & 0x100)>>8;
	*subaddress         = (MEM(current_sp + 4) & 0x1f);
	*bytes_len          = MEM(current_sp + 5);
	Low_address         = MEM(current_sp + 6);
	High_address        =  MEM(current_sp + 7);
	*Data_Block_Address = Low_address | (High_address<<16);

	return MEM(current_sp);
}

//获取当前栈指针地址
Uint16 get_current_sp(void)
{
    return MEM(GLINK_NT_SP);
}

//返回发送端NC ID、子地址、字节长度、接收地址等信息
Uint16 get_sp_Target_NC_ID(const Uint16 current_sp,Uint16* NC_ID,Uint16* TR,Uint16* subaddress,Uint16* bytes_len,Uint32* Data_Block_Address)
{
    Uint16 Low_address,High_address;

    *NC_ID              = (MEM(current_sp + 1) & 0xfff);
    *TR                 = (MEM(current_sp + 4) & 0x100)>>8;
    *subaddress         = (MEM(current_sp + 4) & 0x1f);
    *bytes_len          = MEM(current_sp + 5);
    Low_address         = MEM(current_sp + 6);
    High_address        = MEM(current_sp + 7);
    *Data_Block_Address = Low_address | (High_address<<16);

    return MEM(current_sp);
}

//子地址忙位配置表
void config_busy_table(Uint16 chanel,Uint16 TR,Uint16 busy_subaddress)
{
    if(TR == 0)    //接收子地址
    {
        if(0<=busy_subaddress<=15)
            MEM(0x200*chanel + 0x30) = 1<<busy_subaddress;
        else if(16<=busy_subaddress<=31)
            MEM(0x200*chanel + 0x31) = 1<<(busy_subaddress-16);
    }
    else {         //发送子地址
        if(0<=busy_subaddress<=15)
            MEM(0x200*chanel + 0x32) = 1<<busy_subaddress;
        else if(16<=busy_subaddress<=31)
            MEM(0x200*chanel + 0x33) = 1<<(busy_subaddress-16);
    }
}
