#include <stdio.h>
#include "GLINK.h"

extern far void vectors();

/*Local software delay function*/
static void PLLDelay(int Count)
{
	 Uint32 i = Count;
	 while(i--){
	     asm(" NOP 1");
	 }
}

//寄存器地址addr写入data值
void GLinkWriteReg(UINT32 addr,UINT16 data);
{
	*(volatile Uint16*)(0XB0000000) = 0xAAAA;
	*(volatile Uint16*)(0XA0000000+(addr<<2)) = data;
}
//存储器地址addr写入data值
void GLinkWriteMem(UINT32 addr,UINT16 data);
{
	*(volatile Uint16*)(0XB0000000) = 0xBBBB;
	*(volatile Uint16*)(0XA0000000+(addr<<2)) = data;
}

void test_SmartNCShort()
{
	// 01 节点软复位
	GLinkWriteReg(0x01,0x0001);

	// 02 设置节点ID，包含域ID，节点ID，最高位奇校验
	GLinkWriteReg(0x00,0x0200);

	// 03 使能A、B通道
	GLinkWriteReg(0x03,0x0003);

	// 04 工作模式使能SmartNC1
	GLinkWriteReg(0x02,0x0010);

	// 05 SmartNC超时设置寄存器
	GLinkWriteReg(0x29,0x8000);

	// 06 SmartNC配置寄存器：bit[10]=1：短报文模式；
	GLinkWriteReg(0x2A,0x0400);

	// 07 设置NT子地址
	*(volatile Uint16*)(0XB0000000+(0x01<<1)) = 0x0001;

	// 08 设置传输配置项，len=0x10，NT接收指令,对1路NT发起访问
	*(volatile Uint16*)(0XB0000000+(0x02<<1)) = 0x1010;

	// 09 设置NT ID，SmartNT1，ID=0x001
	*(volatile Uint16*)(0XB0000000+(0x03<<1)) = 0x4001;

	// 10 触发SmartNC发送
	*(volatile Uint16*)(0XB0000000+(0x00<<1)) = 0x1111;

	while(1){}
}

void test_SmartNCLong()
{
	// 01 节点软复位
	GLinkWriteReg(0x01,0x0001);

	// 02 设置节点ID，包含域ID，节点ID，最高位奇校验
	GLinkWriteReg(0x00,0x0200);

	// 03 使能A、B通道
	GLinkWriteReg(0x03,0x0003);

	// 04 工作模式使能SmartNC1
	GLinkWriteReg(0x02,0x0010);

	// 05 SmartNC超时设置寄存器
	GLinkWriteReg(0x29,0x8000);

	// 06 SmartNC配置寄存器：bit[10]=0：长报文模式；
	GLinkWriteReg(0x2A,0x0000);

	// 07 设置数据长度高字
	*(volatile Uint16*)(0XB0000000+(0x01<<1)) = 0x0001;

	// 08 设置数据长度低字
	*(volatile Uint16*)(0XB0000000+(0x02<<1)) = 0x0010;

	// 09 设置NT ID，SmartNT，ID=0x001
	*(volatile Uint16*)(0XB0000000+(0x03<<1)) = 0x0001;

	// 10 触发SmartNC发送
	*(volatile Uint16*)(0XB0000000+(0x00<<1)) = 0x1111;

	while(1){}
}

void test_SmartNTShort()
{
	// 01 节点软复位
	GLinkWriteReg(0x01,0x0001);

	// 02 设置节点ID，包含域ID，节点ID，最高位奇校验
	GLinkWriteReg(0x00,0x0200);

	// 03 使能A、B通道
	GLinkWriteReg(0x03,0x0003);

	// 04 SmartNT1短报文，无需配对NC ID
	GLinkWriteReg(0x3C,0x4000);

	// 05 工作模式使能SmartNT1
	GLinkWriteReg(0x02,0x0100);

	while(1){}

}

void test_SmartNTLong()
{
	// 01 节点软复位
	GLinkWriteReg(0x01,0x0001);

	// 02 设置节点ID，包含域ID，节点ID，最高位奇校验
	GLinkWriteReg(0x00,0x0200);

	// 03 使能A、B通道
	GLinkWriteReg(0x03,0x0003);

	// 04 SmartNT1长报文，配对SmartNC1 ID=0x3C
	GLinkWriteReg(0x3C,0x0001);

	// 05 工作模式使能SmartNT1
	GLinkWriteReg(0x02,0x0100);

	while(1){}
}

void test_NM()
{
	// 01 节点软复位
	GLinkWriteReg(0x01,0x0001);

	// 02 设置节点ID，包含域ID，节点ID，最高位奇校验
	GLinkWriteReg(0x00,0x0200);

	// 03 使能A、B通道
	GLinkWriteReg(0x03,0x0003);

	// 04 工作模式使能NM
	GLinkWriteReg(0x02,0x2000);

	// 05监听设置寄存器  不记录错误帧、监听过滤禁止
	GLinkWriteReg(0x40,0x0000);
	
	// 06触发NM记录功能
	GlinkWriteReg(0x01,0x0400);

	while(1){}
}


void test(void)
{
	// 01 SmartNC短报文测试
	test_SmartNCShort();
	
	// 02 SmartNC长报文测试
	//	test_SmartNCLong();

	// 03 SmartNT短报文测试
	//	test_SmartNTShort();

	// 04 SmartNT长报文测试
	//	test_SmartNTLong();

	// 05 NM测试
	//	test_NM();

}








