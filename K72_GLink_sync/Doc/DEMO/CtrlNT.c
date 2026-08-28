/*
 * ctrlNT.c
 *
 *  Created on: 2023-7-26
 *      Author: baozhong
 *  说 明：ctrlNT接收数据和被拉取数据
 *  注意：本例子仅供参考，实际使用需要参考软件手册
 */
#include "JLK1263.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "GPIO.h"
#include <stdbool.h>

#define  Remote_ID  0x3                   //对端ID号，从Remote_ID拉取数据和向Remote_ID发送数据

#define  Local_ID    0x8                   //本地节点ID=3,网络域=3
#define  word_num    32             //要发送的word个数，字节数=字个数*2

void ctrlNT(void)
{
	Uint16 i = 0;
	Uint16 status = 0;
	Uint16  NT_STACKBASE = 0xa000; //NT堆栈指针起始位置

	/*收到的数据信息*/
	Uint16  remote_NC_ID = 0;
	Uint16  TR           = 0;
	Uint16  subaddress   = 0;
	Uint16  len          = 0;
	Uint32  Data_Block_Address  = 0;
    /*NT端发送和接收地址*/
    Uint32 NT_recv_memory = 0x5000;                     //NT接收栈内存地址
    Uint32 NT_send_memory = 0x6000;                     //NT接收内存地址

	MemorySpaceInit();

	configID(Local_ID);
	configchanelEnable(0xc3);         //使能通道A和B，和环功能
	configInteruptMode(0x2);          //配置 脉冲 中断，自动清除
	configInteruptMask(0x800);        //使能控制流NT交换结束中断
	configtimestamp(5);		          //timetag 1us
	configctrlNT(0xA0,0x1c);           //设置控制流NT寄存器1、2

	configNTSP(NT_STACKBASE);
	/**通道1*/
	configctrlNTchanel(1,0,Remote_ID);                       //第一路控制流NT使能，设置配对的NC的02的ctrlnc1
	config_recv_ctrlnt_memory(1,0,0,0x200,1,NT_recv_memory);   //A区域接收，接收子地址交换结束中断使能，接收数据地址0x5000
	config_send_ctrlnt_memory(1,1,NT_send_memory); 		      //发送数据地址0x6000

	//工作模式配置,ctrlNT
	config_workmode(0,0,1,0,0,0,0,0,0,0,0,0);

    //初始化被拉取的数据
	for(i=0;i<256;i++)
		MEM(NT_send_memory+i)= 0x8888;

	while(1){
		if(getInteruptStatus() == 0x800)    //接收中断
		{
			status = get_current_Target_NC_ID(&remote_NC_ID,&TR,&subaddress,&len,&Data_Block_Address);
            printf("NC =0x%x,TR = %d,subaddress = 0x%x,len = %d,data_address = 0x%x\r\n",remote_NC_ID,TR,subaddress,len,(Uint16)Data_Block_Address);
            if(TR == 0)
                printf("NT接收数据 = %x\r\n",MEM(Data_Block_Address));
            else if(TR == 1)
                printf("NT被拉取数据 = %x\r\n",MEM(Data_Block_Address));
		}
	}
}
