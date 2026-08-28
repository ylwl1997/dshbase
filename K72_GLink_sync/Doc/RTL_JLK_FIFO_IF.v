`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company:
// =======================================================================
// CETC-58
// =======================================================================
// File Name      : JLK_FIFO_IF.v
// Module         : JLK_FIFO_IF
// -----------------------------------------------------------------------
// Update History :
// -----------------------------------------------------------------------
// Rev.Level  Date         Coded by         Contents
// 0.2.0   2023/05/09       xiongx          created
//
// =======================================================================
// End Revision
// =======================================================================

// =================================================================================================
// Module Header
// =================================================================================================

module JLK_FIFO_IF (
    input                               SYS_CLK               , // 125M
    input                               RST_N                 , // low reset

    output                              WC_FIFO_RD_EN         ,
    input                               WC_FIFO_EMPTY         ,
    input            [33:0]             WC_FIFO_DOUT          ,

    output                              WD_FIFO_RD_EN         ,
    input                               WD_FIFO_EMPTY         ,
    input            [15:0]             WD_FIFO_DOUT          ,

    output                              RC_FIFO_WR_EN         ,
    output           [33:0]             RC_FIFO_DIN           ,

    output                              RD_FIFO_WR_EN         ,
    output           [15:0]             RD_FIFO_DIN           ,

    output                              SMARTNC1_TRIG         ,
    input                               SMARTNC1_IDLE         ,
    input                               SMARTNC1_AFULL        ,
    input                               SMARTNC1_EMPTY        ,
//    input                               SMARTNC1_ERR          ,

    input                               SMARTNT1_REQ          ,
    input                               SMARTNT1_EMPTY        ,
    output                              SMARTNT1_ACK          ,
//    input                               SMARTNT1_ERR          ,

    output                              SMARTNC2_TRIG         ,
    input                               SMARTNC2_IDLE         ,
    input                               SMARTNC2_AFULL        ,
    input                               SMARTNC2_EMPTY        ,
//    input                               SMARTNC2_ERR          ,

    input                               SMARTNT2_REQ          ,
    input                               SMARTNT2_EMPTY        ,
    output                              SMARTNT2_ACK          ,
//    input                               SMARTNT2_ERR          ,

    output           [15:0]             JLK_FIFO_WDATA        ,
    output                              JLK_FIFO_WR           ,
    output                              JLK_FIFO_RD           ,
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    input            [15:0]             JLK_FIFO_RDATA        ,

    input                               NT1_SEND_FLAG         ,
    input                               NT2_SEND_FLAG         ,

    input            [ 8:0]             NT1_SEND_NUM          ,
    input            [ 8:0]             NT2_SEND_NUM          ,

    output                              NT_SEND_RAM_ENA       ,
    output                              NT_SEND_RAM_WEA       , // 1 WRITE 0 READ
    output           [ 7:0]             NT_SEND_RAM_ADDR      ,
    input            [15:0]             NT_SEND_RAM_DOUT      ,

    output                              NC1_DONE              ,
    output                              NC2_DONE              ,
    output                              NT1_DONE              ,
    output                              NT2_DONE

    ) ;

// =================================================================================================
// Defination of Internal Signals
// =================================================================================================

    //---------------------------------------------------------------------
    // Defination of Parameter
    //---------------------------------------------------------------------

    // JLK FIFO WR FSM
    parameter                           P_TX_IDLE           = 8'b0000_0001   ;
    parameter                           P_WR_CMD            = 8'b0000_0010   ;
    parameter                           P_CMD_CHK           = 8'b0000_0100   ;
    parameter                           P_NC_TRIG_GEN       = 8'b0000_1000   ;
    parameter                           P_NC_IDLE_WAIT      = 8'b0001_0000   ;
    parameter                           P_NC_SEND           = 8'b0010_0000   ;
    parameter                           P_NC_TX_DONE        = 8'b0100_0000   ;
    parameter                           P_TX_END            = 8'b1000_0000   ;

    // JLK FIFO RD FSM
    parameter                           P_RX_IDLE           = 9'b0_0000_0001 ;
    parameter                           P_NC_READ           = 9'b0_0000_0010 ;
    parameter                           P_NC_RX_DONE        = 9'b0_0000_0100 ;
    parameter                           P_NT_EMPTY_WAIT     = 9'b0_0000_1000 ;
    parameter                           P_NT_READ           = 9'b0_0001_0000 ;
    parameter                           P_NT_RX_CHECK       = 9'b0_0010_0000 ;
    parameter                           P_NT_SEND           = 9'b0_0100_0000 ;
    parameter                           P_NT_ACK_GEN        = 9'b0_1000_0000 ;
    parameter                           P_RX_END            = 9'b1_0000_0000 ;

    //---------------------------------------------------------------------
    // Defination of Internal Signals
    //---------------------------------------------------------------------

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [ 9:0]             r_tx_fsm_state                ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [ 9:0]             r_rx_fsm_state                ;

    reg                                 r_wc_fifo_empty               ;
    reg                                 r_wc_fifo_rd_en               ;
    reg              [33:0]             r_wc_fifo_dout                ;

    reg                                 r_nc1_tx_flag                 ;
    reg                                 r_nc2_tx_flag                 ;
    reg                                 r_nt1_send_flag               ;
    reg                                 r_nt2_send_flag               ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_smartnc1_trig               ;
    reg                                 r_smartnc2_trig               ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_smartnc1_idle               ;
    reg                                 r_smartnc2_idle               ;

    reg                                 r_wd_fifo_rd_en               ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire                                s_wd_fifo_rd_en               ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire             [15:0]             s_wd_fifo_dout                ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [31:0]             r_send_cnt                    ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_nc1_done                    ;
    reg                                 r_nc2_done                    ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_smartnt1_req                ;
    reg                                 r_smartnt2_req                ;
//    wire                                s_smartnt1_req_pos            ;
//    wire                                s_smartnt2_req_pos            ;

    reg                                 r_nc1_rx_flag                 ;
    reg                                 r_nc2_rx_flag                 ;
    reg                                 r_nt1_rx_flag                 ;
    reg                                 r_nt2_rx_flag                 ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_rd_fifo_wr_en               ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [15:0]             r_rd_fifo_din                 ;
//    reg              [15:0]             r_rd_fifo_din_d1              ;
    reg                                 r_rd_fifo_wr_en_d1            ;
    wire                                s_rd_fifo_wr_en_pos           ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_rc_fifo_wr_en               ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [33:0]             r_rc_fifo_din                 ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_smartnt1_ack                ;
    reg                                 r_smartnt2_ack                ;

    // for debug
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire                                s_wd_fifo_empty               ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire                                s_smartnt1_empty              ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire                                s_smartnc1_empty              ;

    reg                                 r_nt_send_ram_ena             ;
    reg                                 r_nt_send_ram_ena_d1          ;
    reg              [15:0]             r_nt_send_ram_addr            ;

// =================================================================================================
// RTL body
// =================================================================================================

    // debug
    assign s_wd_fifo_empty  = WD_FIFO_EMPTY  ;
    assign s_smartnt1_empty = SMARTNT1_EMPTY ;
    assign s_smartnc1_empty = SMARTNC1_EMPTY ;

    //-----------------------------------------------
    // JLK FIFO SEND FSM
    //-----------------------------------------------
    // SEND FSM
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_tx_fsm_state <= P_TX_IDLE ;
        end else begin

            case ( r_tx_fsm_state )
                P_TX_IDLE      : begin
                    if ( r_wc_fifo_empty == 1'b0 ) begin
                        r_tx_fsm_state <= P_WR_CMD ;
                    end
                end

                P_WR_CMD    : begin
                    r_tx_fsm_state <= P_CMD_CHK ;
                end

                P_CMD_CHK   : begin
                    if ( r_nc1_tx_flag | r_nc2_tx_flag ) begin
                        r_tx_fsm_state <= P_NC_TRIG_GEN ;
                    end
                end

                P_NC_TRIG_GEN   : begin
                    r_tx_fsm_state <= P_NC_IDLE_WAIT ;
                end

                P_NC_IDLE_WAIT  : begin
                    if ( (r_nc1_tx_flag == 1'b1 && r_smartnc1_idle == 1'b0) || (r_nc2_tx_flag == 1'b1 && r_smartnc2_idle == 1'b0) ) begin
                        r_tx_fsm_state <= P_NC_SEND ;
                    end
                end

                P_NC_SEND       : begin
                    if ( s_wd_fifo_rd_en == 1'b1 && r_send_cnt == 1'b1 ) begin
                        r_tx_fsm_state <= P_NC_TX_DONE ;
                    end
                end

                P_NC_TX_DONE    : begin
                    r_tx_fsm_state <= P_TX_END ;
                end

                P_TX_END        : begin
                    r_tx_fsm_state <= P_TX_IDLE ;
                end

                default         : begin
                    r_tx_fsm_state <= P_TX_IDLE ;
                end
            endcase

        end
    end

    // IDLE
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wc_fifo_empty <= 1'b1            ;
        end else begin
            r_wc_fifo_empty <= WC_FIFO_EMPTY   ;
        end
    end

    // P_WR_CMD
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wc_fifo_rd_en <= 1'b0            ;
        end else begin
            if ( r_tx_fsm_state == P_WR_CMD ) begin
                r_wc_fifo_rd_en <= 1'b1        ;
            end else begin
                r_wc_fifo_rd_en <= 1'b0        ;
            end
        end
    end

    assign WC_FIFO_RD_EN = r_wc_fifo_rd_en ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wc_fifo_dout <= 34'b0            ;
        end else begin
            r_wc_fifo_dout <= WC_FIFO_DOUT     ;
        end
    end

    // P_CMD_CHK
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nc1_tx_flag <= 1'b0 ;
            r_nc2_tx_flag <= 1'b0 ;
        end else begin
            if ( (r_tx_fsm_state == P_CMD_CHK) && (r_wc_fifo_dout[33:32] == 2'b00) ) r_nc1_tx_flag <= 1'b1 ; else if (r_tx_fsm_state == P_NC_TX_DONE) r_nc1_tx_flag <= 1'b0 ;
            if ( (r_tx_fsm_state == P_CMD_CHK) && (r_wc_fifo_dout[33:32] == 2'b01) ) r_nc2_tx_flag <= 1'b1 ; else if (r_tx_fsm_state == P_NC_TX_DONE) r_nc2_tx_flag <= 1'b0 ;
        end
    end

    // P_NC_TRIG_GEN
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_smartnc1_trig <= 1'b0 ;
        end else begin
            if ( (r_tx_fsm_state == P_NC_TRIG_GEN) && (r_nc1_tx_flag == 1'b1) ) begin
                r_smartnc1_trig <= 1'b1 ;
            end else begin
                r_smartnc1_trig <= 1'b0 ;
            end
        end
    end

    assign SMARTNC1_TRIG = r_smartnc1_trig ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_smartnc2_trig <= 1'b0 ;
        end else begin
            if ( (r_tx_fsm_state == P_NC_TRIG_GEN) && (r_nc2_tx_flag == 1'b1) ) begin
                r_smartnc2_trig <= 1'b1 ;
            end else begin
                r_smartnc2_trig <= 1'b0 ;
            end
        end
    end

    assign SMARTNC2_TRIG = r_smartnc2_trig ;

    // P_NC_IDLE_WAIT
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_smartnc1_idle <= 1'b1 ;
            r_smartnc2_idle <= 1'b1 ;
        end else begin
            r_smartnc1_idle <= SMARTNC1_IDLE ;
            r_smartnc2_idle <= SMARTNC2_IDLE ;
        end
    end

    // P_NC_SEND / P_NT_SEND
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wd_fifo_rd_en <= 1'b0 ;
        end else begin
//            if ( (r_tx_fsm_state == P_NC_SEND) || (r_rx_fsm_state == P_NT_SEND) ) begin
            if ( r_tx_fsm_state == P_NC_SEND ) begin
                if ( ( r_wd_fifo_rd_en == 1'b1 && r_send_cnt == 1'b1 ) ) begin
                    r_wd_fifo_rd_en <= 1'b0 ;
                end else begin
                    r_wd_fifo_rd_en <= 1'b1 ;
                end
            end
        end
    end

//    assign s_wd_fifo_rd_en = ( r_nc1_tx_flag   ) ? ( r_wd_fifo_rd_en & ~WD_FIFO_EMPTY & ~SMARTNC1_AFULL ) :
//                             ( r_nc2_tx_flag   ) ? ( r_wd_fifo_rd_en & ~WD_FIFO_EMPTY & ~SMARTNC2_AFULL ) :
//                             ( r_nt1_send_flag ) ? ( r_wd_fifo_rd_en & ~WD_FIFO_EMPTY ) :
//                             ( r_nt2_send_flag ) ? ( r_wd_fifo_rd_en & ~WD_FIFO_EMPTY ) : 1'b0 ;
    assign s_wd_fifo_rd_en = ( r_nc1_tx_flag ) ? ( r_wd_fifo_rd_en & ~WD_FIFO_EMPTY & ~SMARTNC1_AFULL ) :
                             ( r_nc2_tx_flag ) ? ( r_wd_fifo_rd_en & ~WD_FIFO_EMPTY & ~SMARTNC2_AFULL ) : 1'b0 ;
    assign WD_FIFO_RD_EN = s_wd_fifo_rd_en ;
//    assign JLK_FIFO_WR   = s_wd_fifo_rd_en ;
    assign JLK_FIFO_WR = ( r_nt1_send_flag | r_nt2_send_flag ) ? r_nt_send_ram_ena_d1 : s_wd_fifo_rd_en ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_send_cnt <= 32'b0  ;
        end else begin
            if ( r_wc_fifo_rd_en ) begin
                r_send_cnt <= r_wc_fifo_dout[31:0] ;
            end else if ( r_rx_fsm_state == P_NT_RX_CHECK && r_nt1_send_flag == 1'b1 ) begin
                r_send_cnt <= NT1_SEND_NUM         ;
            end else if ( r_rx_fsm_state == P_NT_RX_CHECK && r_nt2_send_flag == 1'b1 ) begin
                r_send_cnt <= NT2_SEND_NUM         ;
            end else if ( s_wd_fifo_rd_en | r_nt_send_ram_ena ) begin
                r_send_cnt <= r_send_cnt - 1'b1    ;
            end
        end
    end

    assign s_wd_fifo_dout = WD_FIFO_DOUT ;
//    assign JLK_FIFO_WDATA = s_wd_fifo_dout ;
    assign JLK_FIFO_WDATA = ( r_nt1_send_flag | r_nt2_send_flag ) ? NT_SEND_RAM_DOUT : s_wd_fifo_dout ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nt_send_ram_ena <= 1'b0 ;
        end else begin
            if ( r_rx_fsm_state == P_NT_SEND ) begin
                if ( r_send_cnt == 1'b1 ) begin
                    r_nt_send_ram_ena <= 1'b0 ;
                end else begin
                    r_nt_send_ram_ena <= 1'b1 ;
                end
            end
        end
    end

    assign NT_SEND_RAM_ENA = r_nt_send_ram_ena ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nt_send_ram_ena_d1 <= 1'b0 ;
        end else begin
            r_nt_send_ram_ena_d1 <= r_nt_send_ram_ena ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nt_send_ram_addr <= 8'b0 ;
        end else begin
            if ( (r_nt_send_ram_addr == 8'd255) || (r_rx_fsm_state == P_NT_SEND && r_nt_send_ram_ena == 1'b0) ) begin
                r_nt_send_ram_addr <= 8'b0 ;
            end else if ( r_nt_send_ram_ena ) begin
                r_nt_send_ram_addr <= r_nt_send_ram_addr + 1'b1 ;
            end
        end
    end

    assign NT_SEND_RAM_ADDR = r_nt_send_ram_addr ;

    // P_NC_TX_DONE
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nc1_done <=  1'b0 ;
        end else begin
            if ( (r_tx_fsm_state == P_NC_TX_DONE) && (r_nc1_tx_flag == 1'b1) ) begin
                r_nc1_done <=  1'b1 ;
            end else begin
                r_nc1_done <=  1'b0 ;
            end
        end
    end

    assign NC1_DONE = r_nc1_done ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nc2_done <=  1'b0 ;
        end else begin
            if ( (r_tx_fsm_state == P_NC_TX_DONE) && (r_nc2_tx_flag == 1'b1) ) begin
                r_nc2_done <=  1'b1 ;
            end else begin
                r_nc2_done <=  1'b0 ;
            end
        end
    end

    assign NC2_DONE = r_nc2_done ;

    //-----------------------------------------------
    // JLK FIFO READ FSM
    //-----------------------------------------------
    // READ FSM
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rx_fsm_state <= P_RX_IDLE ;
        end else begin

            case ( r_rx_fsm_state )
                P_RX_IDLE       : begin
                    if ( (SMARTNC1_EMPTY == 1'b0) || (SMARTNC2_EMPTY == 1'b0) ) begin
                        r_rx_fsm_state <= P_NC_READ       ;
                    end else if ( (r_smartnt1_req == 1'b1 && SMARTNT1_EMPTY == 1'b0) || (r_smartnt2_req == 1'b1 && SMARTNT2_EMPTY == 1'b0) ) begin
                        r_rx_fsm_state <= P_NT_READ ;
                    end
                end

                P_NC_READ       : begin
                    if ( (r_nc1_rx_flag == 1'b1 && SMARTNC1_EMPTY == 1'b1) || (r_nc2_rx_flag == 1'b1 && SMARTNC2_EMPTY == 1'b1) ) begin
                        r_rx_fsm_state <= P_NC_RX_DONE ;
                    end
                end

                P_NC_RX_DONE    : begin
                    r_rx_fsm_state <= P_RX_END ;
                end

//                P_NT_EMPTY_WAIT : begin
//                    if ( (SMARTNT1_EMPTY == 1'b0) || (SMARTNT2_EMPTY == 1'b0) ) begin
//                        r_rx_fsm_state <= P_NT_READ ;
//                    end
//                end

                P_NT_READ       : begin
                    if ( (r_nt1_rx_flag == 1'b1 && SMARTNT1_EMPTY == 1'b1) || (r_nt2_rx_flag == 1'b1 && SMARTNT2_EMPTY == 1'b1) ) begin
                        r_rx_fsm_state <= P_NT_RX_CHECK ;
                    end
                end

                P_NT_RX_CHECK   : begin
                    if ( r_nt1_send_flag | r_nt2_send_flag ) begin
                        r_rx_fsm_state <= P_NT_SEND ;
                    end else begin
                        r_rx_fsm_state <= P_RX_END ;
                    end
                end

                P_NT_SEND       : begin
                    if ( r_nt_send_ram_ena == 1'b1 && r_send_cnt == 1'b1 ) begin
                        r_rx_fsm_state <= P_NT_ACK_GEN ;
                    end
                end

                P_NT_ACK_GEN    : begin
                    r_rx_fsm_state <= P_RX_END ;
                end

                P_RX_END        :begin
                    r_rx_fsm_state <= P_RX_IDLE ;
                end

                default         : begin
                    r_rx_fsm_state <= P_RX_IDLE ;
                end
            endcase

        end
    end

    // P_RX_IDLE
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_smartnt1_req <= 1'b0 ;
            r_smartnt2_req <= 1'b0 ;
        end else begin
            r_smartnt1_req <= SMARTNT1_REQ ;
            r_smartnt2_req <= SMARTNT2_REQ ;
        end
    end

//    assign s_smartnt1_req_pos = ~r_smartnt1_req & SMARTNT1_REQ ;
//    assign s_smartnt2_req_pos = ~r_smartnt2_req & SMARTNT2_REQ ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nc1_rx_flag <= 1'b0 ;
            r_nc2_rx_flag <= 1'b0 ;
            r_nt1_rx_flag <= 1'b0 ;
            r_nt2_rx_flag <= 1'b0 ;
        end else begin
            if ( (r_rx_fsm_state == P_RX_IDLE) && (SMARTNC1_EMPTY == 1'b0) ) r_nc1_rx_flag <= 1'b1 ; else if (r_rx_fsm_state == P_NC_RX_DONE) r_nc1_rx_flag <= 1'b0 ;
            if ( (r_rx_fsm_state == P_RX_IDLE) && (SMARTNC2_EMPTY == 1'b0) ) r_nc2_rx_flag <= 1'b1 ; else if (r_rx_fsm_state == P_NC_RX_DONE) r_nc2_rx_flag <= 1'b0 ;
//            if ( (r_rx_fsm_state == P_NT_EMPTY_WAIT) && (SMARTNT1_EMPTY == 1'b0) ) r_nt1_rx_flag <= 1'b1 ; else if (r_rx_fsm_state == P_NT_ACK_GEN) r_nt1_rx_flag <= 1'b0 ;
//            if ( (r_rx_fsm_state == P_NT_EMPTY_WAIT) && (SMARTNT2_EMPTY == 1'b0) ) r_nt2_rx_flag <= 1'b1 ; else if (r_rx_fsm_state == P_NT_ACK_GEN) r_nt2_rx_flag <= 1'b0 ;
            if ( (r_rx_fsm_state == P_NT_READ) && (SMARTNT1_EMPTY == 1'b0) ) r_nt1_rx_flag <= 1'b1 ; else if (r_rx_fsm_state == P_RX_END) r_nt1_rx_flag <= 1'b0 ;
            if ( (r_rx_fsm_state == P_NT_READ) && (SMARTNT2_EMPTY == 1'b0) ) r_nt2_rx_flag <= 1'b1 ; else if (r_rx_fsm_state == P_RX_END) r_nt2_rx_flag <= 1'b0 ;
        end
    end

    // P_NC_READ / P_NT_READ
    assign JLK_FIFO_RD = ( ( (r_rx_fsm_state == P_NC_READ)||(r_rx_fsm_state == P_NT_READ) ) && ( (SMARTNT1_EMPTY == 1'b0)||(SMARTNT2_EMPTY == 1'b0) ) ) ? 1'b1 : 1'b0 ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rd_fifo_wr_en <= 1'b0 ;
        end else begin
            if ( (r_rx_fsm_state == P_NC_READ) || (r_rx_fsm_state == P_NT_READ) ) begin
                r_rd_fifo_wr_en <= 1'b1 ;
            end else begin
                r_rd_fifo_wr_en <= 1'b0 ;
            end
        end
    end

    assign RD_FIFO_WR_EN = r_rd_fifo_wr_en & ( ~SMARTNT1_EMPTY | ~SMARTNT2_EMPTY );

//    always @(posedge SYS_CLK or negedge RST_N) begin
//        if (!RST_N) begin
//            r_rd_fifo_din    <= 16'b0          ;
//            r_rd_fifo_din_d1 <= 16'b0          ;
//        end else begin
//            r_rd_fifo_din    <= JLK_FIFO_RDATA ;
//            r_rd_fifo_din_d1 <= r_rd_fifo_din  ;
//        end
//    end

    assign RD_FIFO_DIN = JLK_FIFO_RDATA ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rd_fifo_wr_en_d1 <= 1'b0            ;
        end else begin
            r_rd_fifo_wr_en_d1 <= r_rd_fifo_wr_en ;
        end
    end

    assign s_rd_fifo_wr_en_pos = ~r_rd_fifo_wr_en_d1 & r_rd_fifo_wr_en ;
//    assign s_rd_fifo_wr_en_neg = ~r_rd_fifo_wr_en & r_rd_fifo_wr_en_d1 ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rc_fifo_wr_en <= 1'b0 ;
        end else begin
            if ( s_rd_fifo_wr_en_pos ) begin
                r_rc_fifo_wr_en <= 1'b1 ;
            end else begin
                r_rc_fifo_wr_en <= 1'b0 ;
            end
        end
    end

    assign RC_FIFO_WR_EN = r_rc_fifo_wr_en ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rc_fifo_din <= 34'b0 ;
        end else begin
            if ( r_nc1_rx_flag == 1'b1 ) r_rc_fifo_din[33:32] <= 2'b00 ;
            if ( r_nc2_rx_flag == 1'b1 ) r_rc_fifo_din[33:32] <= 2'b01 ;
            if ( r_nt1_rx_flag == 1'b1 ) r_rc_fifo_din[33:32] <= 2'b10 ;
            if ( r_nt2_rx_flag == 1'b1 ) r_rc_fifo_din[33:32] <= 2'b11 ;
        end
    end

    assign RC_FIFO_DIN = r_rc_fifo_din ;

    // P_NT_RX_CHECK
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nt1_send_flag <= 1'b0 ;
            r_nt2_send_flag <= 1'b0 ;
        end else begin
            r_nt1_send_flag <= NT1_SEND_FLAG ;
            r_nt2_send_flag <= NT2_SEND_FLAG ;
        end
    end

    // P_NT_ACK_GEN
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_smartnt1_ack <= 1'b0 ;
        end else begin
            if ( (r_rx_fsm_state == P_NT_ACK_GEN) && (r_nt1_rx_flag == 1'b1) ) begin
                r_smartnt1_ack <= 1'b1 ;
            end else begin
                r_smartnt1_ack <= 1'b0 ;
            end
        end
    end

    assign SMARTNT1_ACK = r_smartnt1_ack ;
    assign NT1_DONE     = r_smartnt1_ack ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_smartnt2_ack <=  1'b0 ;
        end else begin
            if ( (r_rx_fsm_state == P_NT_ACK_GEN) && (r_nt2_rx_flag == 1'b1) ) begin
                r_smartnt2_ack <=  1'b1 ;
            end else begin
                r_smartnt2_ack <=  1'b0 ;
            end
        end
    end

    assign SMARTNT2_ACK = r_smartnt2_ack ;
    assign NT2_DONE     = r_smartnt2_ack ;


endmodule