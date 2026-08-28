
library ieee;
	use ieee.std_logic_1164.all;
	use ieee.std_logic_unsigned.all;
	use ieee.numeric_std.all;

--smartnc_short	JLK1263_Demo
entity smartnc_shortmsg_demo is	
	port(
		clk					:	in	std_logic;
		rst_n				:	in	std_logic;
		
		-- input signal
		i_subaddress		:	in	std_logic_vector(15 downto 0);
		i_conf				:	in	std_logic_vector(15 downto 0);
		i_NT1_ID			:	in	std_logic_vector(15 downto 0);
		i_trigger			:	in	std_logic;							-- trig transport
		
		-- smartnc signal
		smartnc1_trig		:	out	std_logic;
		smartnc1_idle		:	in	std_logic;
		smartnc1_err		:	in	std_logic;
		smartnc1_afull		:	in	std_logic;
		smartnc1_empty		:	in	std_logic;

		-- fifo signal
		fifo1_wdata			:	out	std_logic_vector(15 downto 0);
		fifo1_wr			:	out	std_logic;
		fifo1_wr_sel_0		:	out	std_logic;
		fifo1_wr_sel_1		:	out	std_logic;
		
		fifo1_rdata			:	in	std_logic_vector(15 downto 0);
		fifo1_rd			:	out	std_logic;
		fifo1_rd_sel_0		:	out	std_logic;
		fifo1_rd_sel_1		:	out	std_logic
	);
end entity smartnc_shortmsg_demo;

architecture trans of smartnc_shortmsg_demo is
component ila_0
	port(
		clk		:	in	std_logic;
		probe0	:	in	std_logic_vector(15 downto 0);
		probe1	:	in	std_logic_vector(31 downto 0);
		probe2	:	in	std_logic;
		probe3	:	in	std_logic_vector(15 downto 0);			-- 16bit
		probe4	:	in	std_logic_vector(15 downto 0);			-- 16bit
		probe5	:	in	std_logic_vector(15 downto 0);			-- 16bit
		probe6	:	in	std_logic_vector(11 downto 0);			-- 12bit
		probe7	:	in	std_logic;								-- 1bit
		probe8	:	in	std_logic;								-- 1bit
		probe9	:	in	std_logic_vector(2 downto 0);			-- 3bit
		probe10	:	in	std_logic;								-- 1bit
		probe11	:	in	std_logic_vector(11 downto 0);			-- 12bit
		probe12	:	in	std_logic;								-- 1bit
		probe13	:	in	std_logic;								-- 1bit
		probe14	:	in	std_logic;								-- 1bit
		probe15	:	in	std_logic;								-- 1bit
		probe16	:	in	std_logic_vector(15 downto 0)			-- 1bit	
	);
end component;
	-- smartnc delay signal
	signal	smartnc1_empty_d	:	std_logic;
	signal	smartnc1_idle_d		:	std_logic;

	-- smartnc edge signal
	signal	smartnc1_empty_pos	:	std_logic;
	signal	smartnc1_empty_neg	:	std_logic;
	signal	smartnc1_idle_pos	:	std_logic;
	signal	smartnc1_idle_neg	:	std_logic;
	signal	smartnc1_sel		:	std_logic;
	
	-- smartnc_trig signal
	signal	i_trigger_d			:	std_logic;						-- 触发数据传输信号打拍信号
	
	signal	r_direction			:	std_logic;						-- 0:NC->NT;1:NT->NC;
	signal	r_send_node_number	:	std_logic_vector(2 downto 0);	-- 发送节点数量
	signal	r_data_number		:	std_logic_vector(11 downto 0);	-- 发送字节长度
	signal	r_data_cnt			:	std_logic_vector(11 downto 0);	-- 计数
	
	signal	i_trigger_pos		:	std_logic;
	signal	i_trigger_neg		:	std_logic;
	
	signal	r_fifo1_rd			:	std_logic;
	signal	r_fifo1_wr			:	std_logic;
	signal	r_fifo1_rdata		:	std_logic_vector(15 downto 0);
	signal	r_fifo1_wdata		:	std_logic_vector(15 downto 0);
	
	signal	r_conf				:	std_logic_vector(15 downto 0);
	signal	r_conf_d			:	std_logic_vector(15 downto 0);
	
	signal	state				:	integer;
	signal	dbg_state			:	std_logic_vector(31 downto 0);
	
	constant	S_IDLE			:	integer	:=	0;
	constant	S_NC_SEND		:	integer	:=	1;
	constant	S_NT_RECV		:	integer	:=	2;
begin

-- dbg inst
dbg_state <= std_logic_vector(to_unsigned(state,dbg_state'length));
ila_inst:ila_0
port map(
	clk		=>	clk					,
	probe0	=>	fifo1_rdata			,	-- 16bit
	probe1	=>	dbg_state			,	-- 32bit
	probe2	=>	i_trigger			,	-- 1bit
	probe3	=>	i_subaddress		,	-- 16bit
	probe4	=>	r_conf				,	-- 16bit
	probe5	=>	i_NT1_ID			,	-- 16bit
	probe6	=>	r_data_cnt			,	-- 12bit
	probe7	=>	r_fifo1_rd			,	-- 1bit
	probe8	=>	r_fifo1_wr			,	-- 1bit
	probe9	=>	r_send_node_number	,	-- 3bit
	probe10	=>	r_direction			,	-- 1bit
	probe11	=>	r_data_number		,	-- 12bit
	probe12	=>	smartnc1_idle		,	-- 1bit
	probe13	=>	smartnc1_err		,	-- 1bitv
	probe14	=>	smartnc1_afull		,	-- 1bit
	probe15	=>	smartnc1_empty		,	-- 1bit
	probe16	=>	r_fifo1_wdata			-- 16bit
	
);

-- i_trigger empty edge
process (clk,rst_n)
begin
	if(rst_n = '0') then
		i_trigger_d		<=	'0';
	elsif(clk'event and clk = '1') then
		i_trigger_d		<=	i_trigger;
	end if;
end process;
i_trigger_pos 	<= 	not(i_trigger_d) 	and  	  	i_trigger;
i_trigger_neg 	<= 		i_trigger_d 	and 	not(i_trigger);


-- smartnc idle edge
process (clk,rst_n)
begin
	if(rst_n = '0') then
		smartnc1_idle_d		<=	'0';
	elsif(clk'event and clk = '1') then
		smartnc1_idle_d		<=	smartnc1_idle;
	end if;
end process;
-- smartnc empty edge
process (clk,rst_n)
begin
	if(rst_n = '0') then
		smartnc1_empty_d		<=	'0';
	elsif(clk'event and clk = '1') then
		smartnc1_empty_d		<=	smartnc1_empty;
	end if;
end process;

smartnc1_empty_pos 	<= 	not(smartnc1_empty_d) 	and  	  	smartnc1_empty;
smartnc1_empty_neg 	<= 		smartnc1_empty_d 	and 	not(smartnc1_empty);
												
smartnc1_idle_pos 	<= 	not(smartnc1_idle_d) 	and  	  	smartnc1_idle;
smartnc1_idle_neg 	<= 		smartnc1_idle_d 	and 	not(smartnc1_idle);
-- smartnc sel signal
smartnc1_sel	<=	'1' ;
			
-- fifo1 rd sel
fifo1_rd_sel_0	<=	'0' when smartnc1_sel = '1' else
					-- '1' when smartnc2_sel = '1' else
					'0' ;
fifo1_rd_sel_1	<=	'0' when smartnc1_sel = '1' else
					-- '0' when smartnc2_sel = '1' else
					'0' ;
-- fifo1 wr sel
fifo1_wr_sel_0	<=	'0' when smartnc1_sel = '1' else
					-- '1' when smartnc2_sel = '1' else
					'0' ;
fifo1_wr_sel_1	<=	'0' when smartnc1_sel = '1' else
					-- '0' when smartnc2_sel = '1' else
					'0' ;


process(clk,rst_n)
begin
	if(rst_n = '0') then
		r_conf_d	<=	x"0000";
		r_conf		<=	x"0000";
	elsif(clk'event and clk = '1') then
		r_conf_d	<=	i_conf;
		r_conf		<=	r_conf_d;
	end if;
end process;				
-- trans direction 0:NC->NT;1:NT->NC;
r_direction	<=	r_conf(15);		

process(rst_n,r_conf)
begin
	if(rst_n = '0') then
		r_send_node_number	<=	"000";
	elsif(r_conf(13 downto 12) = "00") then
		r_send_node_number	<=	"100";
	else
		r_send_node_number	<=	'0' & r_conf(13 downto 12);
	end if;
end process;

process(rst_n,r_conf)
begin
	if(rst_n = '0') then
		r_data_number	<=	x"000";
	elsif(r_conf(8 downto 0) = "000000000") then
		r_data_number	<=	x"100";
	else
		r_data_number	<=	"0000" & ( r_conf(8 downto 1) + r_conf(0) );
	end if;
end process;


process(clk,rst_n)
begin
	if(rst_n = '0') then
		smartnc1_trig	<=	'0';
	elsif(clk'event and clk = '1') then
		if(smartnc1_sel = '1' and i_trigger_pos = '1') then
			smartnc1_trig	<=	'1';
		else
			smartnc1_trig	<=	'0';
		end if;
	end if;
end process;

-- 状态机状态转换
process (clk,rst_n)
begin
	if(rst_n = '0') then
		state	<=	S_IDLE;
	elsif(clk'event and clk = '1') then
		if(	state = S_IDLE and
			smartnc1_idle_neg = '1') then
			state	<=	S_NC_SEND;
		-- S_NC_SEND NC->NT
		elsif(	state = S_NC_SEND and 
				r_direction = '0' and
				r_data_cnt = 2 + r_send_node_number + r_data_number and
				r_fifo1_wr = '1'
		) then
			state	<=	S_NT_RECV;
		-- S_NC_SEND NT->NC
		elsif(	state = S_NC_SEND and
				r_direction = '1' and
				r_data_cnt = 2 + r_send_node_number and
				r_fifo1_wr = '1'
		) then
			state	<=	S_NT_RECV;
		-- S_NT_RECV
		elsif(	state = S_NT_RECV and
				r_data_cnt = 2 + r_send_node_number + r_data_number + 3 and
				r_fifo1_rd = '1'
		) then
			state	<=	S_IDLE;
		elsif(	smartnc1_idle = '1' and
				smartnc1_empty = '1'
		) then
			state	<=	S_IDLE;
		end if;
	end if;
end process;

-- fifo1_wdata
fifo1_wdata	<=	r_fifo1_wdata;
process (clk,rst_n)
begin
	if(rst_n = '0') then
		r_fifo1_wdata	<=	x"0000";
	elsif(clk'event and clk = '1') then
		if(state = S_IDLE) then
			r_fifo1_wdata	<=	x"0000";
		elsif(state = S_NC_SEND and smartnc1_sel = '1') then
			if(r_data_cnt = x"000") then
				r_fifo1_wdata	<=	i_subaddress;
			elsif(r_data_cnt = x"001") then
				r_fifo1_wdata	<=	i_conf;
			elsif(r_data_cnt = x"002") then
				r_fifo1_wdata 	<=	i_NT1_ID;
			else
				r_fifo1_wdata	<=	"0000" & r_data_cnt - 2 - r_send_node_number;	-- 发送递增数，从0开始
			end if;
		end if;
	end if;
end process;

-- fifo1_wr
fifo1_wr	<=	r_fifo1_wr;
process (clk,rst_n)
begin
	if(rst_n = '0') then
		r_fifo1_wr	<=	'0';
	elsif(clk'event and clk = '1') then
		if(	state = S_NC_SEND and 
			not(smartnc1_afull) = '1' and
			r_direction = '0' and
			r_data_cnt < 2 + r_send_node_number + r_data_number
		) then
			r_fifo1_wr	<=	'1';
		elsif(	state = S_NC_SEND and
			not(smartnc1_afull) = '1' and
				r_direction = '1' and
				r_data_cnt < 2 + r_send_node_number
		) then
			r_fifo1_wr	<=	'1';
		else
			r_fifo1_wr	<=	'0';
		end if;
	end if;
end process;


process (clk,rst_n)
begin
	if(rst_n = '0') then
		r_fifo1_rdata	<=	x"0000";
	elsif(clk'event and clk = '1') then
		r_fifo1_rdata	<=	fifo1_rdata;
	end if;
end process;

-- fifo1_rd
fifo1_rd		<=	r_fifo1_rd;
process (clk,rst_n)
begin
	if(rst_n = '0') then
		r_fifo1_rd	<=	'0';
	elsif(clk'event and clk = '1') then
		if(	state = S_NT_RECV and 
			not(smartnc1_empty) = '1' and
			r_data_cnt < 2 + r_send_node_number + r_data_number + 3
		) then
			r_fifo1_rd	<=	'1';
		else
			r_fifo1_rd	<=	'0';
		end if;
	end if;
end process;

-- 计数
process (clk,rst_n)
begin
	if(rst_n = '0') then
		r_data_cnt	<=	x"000";
	elsif(clk'event and clk = '1') then
		if(state = S_IDLE) then
			r_data_cnt	<=	x"000";
		-- NC SEND
		elsif(state = S_NC_SEND) then
			if(	not(smartnc1_afull) = '1' and
				r_direction = '0' and
				r_data_cnt < 2 + r_send_node_number + r_data_number
			) then
				r_data_cnt	<=	r_data_cnt	+	1;
			elsif(	not(smartnc1_afull) = '1' and
					r_direction = '1' and
					r_data_cnt < 2 + r_send_node_number
			) then
				r_data_cnt	<=	r_data_cnt	+	1;
			end if;
		-- NT RECV
		elsif(state = S_NT_RECV) then
			if(	not(smartnc1_empty) = '1' and
				r_data_cnt < 2 + r_send_node_number + r_data_number + 3
			) then	
				r_data_cnt	<=	r_data_cnt	+	1;
			end if;
		end if;
	end if;
end process;


end architecture trans;