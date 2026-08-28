#ifndef _SERDES_H_
#define _SERDES_H_

#include <stdbool.h>

#ifdef __cplusplus
 extern "C" {
#endif /* __cplusplus */

#include <tistdtypes.h>

#define  NC_NT    0
#define  NT_NC    1

#define  Reg_Base_Address   			 0xA0000000      //寄存器基址
#define  Mem_Base_Address                0xA0100000      //存储器基址

#define  REG(x)                          *(volatile Uint16*)(Reg_Base_Address + ((x)<<2))
#define  MEM(x)                          *(volatile Uint16*)(Mem_Base_Address + ((x)<<2))


#define  AddressRST                      *(volatile Uint16*)(0xB0000000)     					 //复位信号
#define  Smart_Base_Address              0xB0000000                                              //smart 模式基地址

#define  Smart_Reg(x)                    *(volatile Uint32*)(Smart_Base_Address + ((x)<<2) )

#define  A_Enable                         0x1
#define  B_Enable                         0x2

//NT
#define  GLINK_NT_SP                     0x0110 				//NT堆栈指针

#define  smartnt_short_frame_recv_mode   1
#define  smartnt_long_frame_recv_mode    0

 /*
  * 第 1 路 SmartNC 超时设置
  */
void config_smartNC1_timeout(Uint16 time_out);

/*
 * 第 1 路 SmartNC 配置
 */
void config_smartNC1(Uint16 reg);

//硬件复位
void reset_1263(void);

//自检
void loopback_test();

//检查通道状态
bool check_chanel_status(char chanel);

/*
 * ID 终端号
 * timestamp NC/NT模式下的时间戳单位，0:32us;1:16us;2:8us;3:4us;4:2us;5:1us
 * interuptMode 中断模式配置，2：脉冲中断；6：电平中断
 * interuptMask 中断屏蔽
 */
void configNC(char ID,char timestamp,char interuptMode,char interuptMask);

//获取控制流状态字
bool getCtrlNcStatusWord(Uint16 stack_address);

//启动发送
void startxmit();

//获取中断状态
Uint16 getInteruptStatus();

//设置节点ID
void configID(Uint16 ID);

//通道使能
void configchanelEnable(Uint16 enable);

//配置中断模式
void configInteruptMode(Uint16 InteruptMode);

//配置中断模式
void configInteruptMask(Uint16 InteruptMask);

//配置时间戳
/*
 * 0:   32us
 * 1:   16us
 * 2:   8us
 * 3:   4us
 * 4:   2us
 * 5:   1us
 */
void configtimestamp(Uint16 timestamp);

/*
 * 配置ctrlNT
 */
void configctrlNT(Uint16 reg1,Uint16 reg2);

/*
 * smartncchanel:对应的nc通道
 * smartncID : 终端ID
 * smartntchanel:1 - 4
 * long_short_mode:1,短报文；0：长报文
 */
void configsmartNTchanel(Uint16 smartntchanel,Uint16 smartncID,Uint16 smartncchanel,Uint16 long_short_mode);

/*
 * chanel:    配置第几路
 * NC_type:  000-第 1 路 CTRLNC；001- 第 2 路 CTRLNC；010-第 1 路 SMARTNC；011-第 2 路 SMARTNC；100-第 3 路 SMARTNC；101- 第 4 路 SMARTNC；
 * ctrlNC_ID: 与第几路通道配对的ctrlNC ID
 */
void configctrlNTchanel(Uint16 chanel,Uint16 NC_type,Uint16 ctrlNC_ID);


//初始化未使用的ctrlNT通道
void InitUnusedctrlNTchanel(Uint16 unused_begin_chanel);

/*
 * smartncchanel:对应的nc通道
 * smartncID : 终端ID
 * smartntchanel:1 - 4
 * long_short_mode:1,短报文；0：长报文
 */
void configsmartNTchanel(Uint16 smartntchanel,Uint16 smartncID,Uint16 smartncchanel,Uint16 long_short_mode);

/*
 * smartncchanel:对应的nc通道
 * smartncID : 终端ID
 * smartntchanel:1 - 4
 * long_short_mode:1,短报文；0：长报文
 */
void configsmartNTchanel(Uint16 smartntchanel,Uint16 smartncID,Uint16 smartncchanel,Uint16 long_short_mode);

/*配置ctrlnt接收地址*/
void config_recv_ctrlnt_memory(Uint16 chanel,Uint16 area,Uint16 service,Uint16 contrl_word, Uint16 subaddress,Uint32 recv_address);

/*配置ctrlnt发送地址*/
void config_send_ctrlnt_memory(Uint16 chanel,Uint16 subaddress,Uint32 send_address);

/*工作模式配置*/
void config_workmode(bool ctrlNC1,bool ctrlNC2,bool ctrlNT,bool smartnc1,bool smartnc2,bool smartnc3,bool smartnc4,bool smartnt1,bool smartnt2,\
		bool smartnt3,bool smartnt4,bool monitor);

/*内存初始化*/
void MemorySpaceInit();

void configNC_Memory_Map(Uint32 stack_address,Uint32 memory_address,Uint16 exch_count);

void ConfigctrlNC_TargetNT(Uint16 memory_address,Uint16 NT1_ID,Uint16 NT2_ID,Uint16 NT3_ID,Uint16 NT4_ID,Uint16 subaddress,\
        bool TR,bool mode,bool state,bool INT,bool retry_en,bool prior,bool one_chanel,bool CH_B,Uint16 NT_num, \
        Uint16 NT1_type,Uint16 NT2_type,Uint16 NT3_type,Uint16 NT4_type,Uint16 Byte_Count);

void startctrlxmit(bool soft_reset,bool ctrlnc1_send,bool ctrlnc2_send);

Uint16 get_exchangeblock_status(Uint32 stack_address);

void ctrlnc_SendData(Uint32 memory_address,Uint16 *Data,Uint16 Byte_Count);

//获取链路状态信息
bool get_chanel_status(char chanel);

//配置NT接收栈地址
void configNTSP(Uint16 stack_address);

//返回发送端NC ID
Uint16 get_current_Target_NC_ID(Uint16* NC_ID,Uint16* TR,Uint16* subaddress,Uint16* bytes_len,Uint32* Data_Block_Address);

//子地址忙位配置表
void config_busy_table(Uint16 chanel,Uint16 TR,Uint16 busy_subaddress);

//获取当前栈指针
Uint16 get_current_sp(void);

//根据用户要求指针，返回发送端NC ID、子地址、字节长度、接收地址等信息
Uint16 get_sp_Target_NC_ID(const Uint16 current_sp,Uint16* NC_ID,Uint16* TR,Uint16* subaddress,Uint16* bytes_len,Uint32* Data_Block_Address);


#ifdef __cplusplus
}
#endif /* __cplusplus */

#endif  /*_SERDES_H_*/
