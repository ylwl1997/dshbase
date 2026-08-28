/*
 * ctrlNC.c
 *
 *  Created on: 2023-7-26
 *      Author: baozhong
 *  说   明: ctrlnc向NT发数，并打印交换状态，910c为未连接状态，800x为链路通路状态。
 *  注意：本例子仅供参考，实际使用需要参考软件手册
 */

#include "JLK1263.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "GPIO.h"
#include <stdbool.h>

#define  Local_ID       0x8003            //本地节点ID=3,网络域=0
#define  Remote_ID      0x6				  //对端id为1

#define  word_num    				32    //要发送的word个数，字节数=字个数*2


/*Local software delay function*/
static void PLLDelay(int Count)
{
	 Uint32 i = Count;
	 while(i--){
	     asm(" NOP 1");
	 }
}


void NC2NT(void)
{
	int i = 0;
	Uint16 status =0;
	Uint16 data[256];

    /*发送栈以及发送地址*/
	Uint32 send_stack_address  = 0x2000;
	Uint32 send_memory_address = 0x5000;

    for(i=0;i<256;i++)
    	data[i] = 0x2000+i;

	MemorySpaceInit();

	configID(Local_ID);       		    //节点ID
	configchanelEnable(0xc3);           //使能通道A和B
	configInteruptMode(0x02);           //配置 脉冲 中断，自动清除
	configInteruptMask(0x04);           //使能控制流NC1特定结束中断
	configtimestamp(5);                 //timetag 1us
	config_ctrlnc1_retry(1,1);                   //使能ctrl1重传，重传2次
	config_workmode(1,0,0,0,0,0,0,0,0,0,0,0);    //设置工作模式

	while(1){
		configNC_Memory_Map(send_stack_address,send_memory_address,1); //配置ctrlNC内存映射

	    //配置ctrl对端的ctrlnt属性，使能中断
	    ConfigctrlNC_TargetNT(send_memory_address,Remote_ID,0,0,0,0x1,\
	            NC_NT,0,0,1,1,1,0,0,1,\
	            0,0,0,0,word_num*2);

	    ctrlnc_SendData(send_memory_address,data,512);                       //写入发送数据
	    startctrlxmit(0,1,0);
	    PLLDelay(1000000);

	    status = get_exchangeblock_status(send_stack_address);            //获取交换状态
		printf("NC send status = 0x%04x\n",status);
	}

}
