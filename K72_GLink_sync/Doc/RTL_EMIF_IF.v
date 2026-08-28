`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company:
// =======================================================================
// CETC-58
// =======================================================================
// File Name      : EMIF_IF.v
// Module         : EMIF_IF
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

module EMIF_IF (
    input                               SYS_CLK               , //
    input                               RST_N                 , // low reset

    input            [ 3:0]             EMIF_CE_N             , // DSP EMIF CE[3]
    input                               EMIF_WE_N             ,
    input                               EMIF_OE_N             ,
    input                               EMIF_RE_N             ,
//    input            [ 3:0]             EMIF_BE_N             ,
    input            [18:0]             EMIF_EA               , // DSP_EMIF ADDR[21:2]
    input            [31:0]             EMIF_ED_IN            ,
    output           [31:0]             EMIF_ED_OUT           ,

    // FIFO SEL
    output                              FIFO1_WR_SEL_0        ,
    output                              FIFO1_WR_SEL_1        ,
    output                              FIFO1_RD_SEL_0        ,
    output                              FIFO1_RD_SEL_1        ,
    output                              FIFO2_WR_SEL_0        ,
    output                              FIFO2_WR_SEL_1        ,
    output                              FIFO2_RD_SEL_0        ,
    output                              FIFO2_RD_SEL_1        ,

    // JLK EMIF
    output                              I_RESET_N             ,
    output           [17:0]             I_CPU_ADDR            ,
    inout            [15:0]             IO_CPU_DQ             ,
    output                              I_SELECT_N            ,
    output                              I_STRBD_N             ,
    output                              I_MEM_ACCESS          ,
    output                              I_RD_ACCESS           ,
    output           [ 2:0]             I_GC_MODE             ,
    output           [ 3:0]             I_CLK_FREQ_SEL        ,

    // WR/RD FIFO
    output                              WC_FIFO1_WR_EN        ,
    output           [33:0]             WC_FIFO1_DIN          ,
    input                               WC_FIFO1_OVERFLOW     ,
    input                               WC_FIFO1_UNDERFLOW    ,

    output                              WD_FIFO1_WR_EN        ,
    output           [15:0]             WD_FIFO1_DIN          ,
    input                               WD_FIFO1_OVERFLOW     ,
    input                               WD_FIFO1_UNDERFLOW    ,
    input            [13:0]             WD_FIFO1_WR_DATA_CNT  ,

    output                              RC_FIFO1_RD_EN        ,
    input            [33:0]             RC_FIFO1_DOUT         ,
    input                               RC_FIFO1_EMPTY        ,
    input                               RC_FIFO1_OVERFLOW     ,
    input                               RC_FIFO1_UNDERFLOW    ,
    input            [13:0]             RC_FIFO1_WR_DATA_CNT  ,

    output                              RD_FIFO1_RD_EN        ,
    input            [15:0]             RD_FIFO1_DOUT         ,
    input                               RD_FIFO1_EMPTY        ,
    input                               RD_FIFO1_OVERFLOW     ,
    input                               RD_FIFO1_UNDERFLOW    ,
    input            [13:0]             RD_FIFO1_WR_DATA_CNT  ,

    output                              WC_FIFO2_WR_EN        ,
    output           [33:0]             WC_FIFO2_DIN          ,
    input                               WC_FIFO2_OVERFLOW     ,
    input                               WC_FIFO2_UNDERFLOW    ,

    output                              WD_FIFO2_WR_EN        ,
    output           [15:0]             WD_FIFO2_DIN          ,
    input                               WD_FIFO2_OVERFLOW     ,
    input                               WD_FIFO2_UNDERFLOW    ,
    input            [13:0]             WD_FIFO2_WR_DATA_CNT  ,

    output                              RC_FIFO2_RD_EN        ,
    input            [33:0]             RC_FIFO2_DOUT         ,
    input                               RC_FIFO2_EMPTY        ,
    input                               RC_FIFO2_OVERFLOW     ,
    input                               RC_FIFO2_UNDERFLOW    ,
    input            [13:0]             RC_FIFO2_WR_DATA_CNT  ,

    output                              RD_FIFO2_RD_EN        ,
    input            [15:0]             RD_FIFO2_DOUT         ,
    input                               RD_FIFO2_EMPTY        ,
    input                               RD_FIFO2_OVERFLOW     ,
    input                               RD_FIFO2_UNDERFLOW    ,
    input            [13:0]             RD_FIFO2_WR_DATA_CNT  ,

    output                              FIFO_RST              ,

    // status
    input                               SMARTNC1_ERR          ,
    input                               SMARTNC2_ERR          ,
    input                               SMARTNC3_ERR          ,
    input                               SMARTNC4_ERR          ,

    input                               SMARTNT1_ERR          ,
    input                               SMARTNT2_ERR          ,
    input                               SMARTNT3_ERR          ,
    input                               SMARTNT4_ERR          ,

    output                              NT1_SEND_FLAG         ,
    output                              NT2_SEND_FLAG         ,
    output                              NT3_SEND_FLAG         ,
    output                              NT4_SEND_FLAG         ,

    output           [ 8:0]             NT1_SEND_NUM          ,
    output           [ 8:0]             NT2_SEND_NUM          ,
    output           [ 8:0]             NT3_SEND_NUM          ,
    output           [ 8:0]             NT4_SEND_NUM          ,

    output                              FIFO1_SEND_RAM_WRITE_ENA ,
    output                              FIFO1_SEND_RAM_WEA    ,
    output           [ 7:0]             FIFO1_SEND_RAM_WRITE_ADDR ,
    output           [15:0]             FIFO1_SEND_RAM_WRITE_DATA ,

    output                              FIFO2_SEND_RAM_WRITE_ENA ,
    output                              FIFO2_SEND_RAM_WEA    ,
    output           [ 7:0]             FIFO2_SEND_RAM_WRITE_ADDR ,
    output           [15:0]             FIFO2_SEND_RAM_WRITE_DATA ,

    input                               NC1_DONE              ,
    input                               NC2_DONE              ,
    input                               NC3_DONE              ,
    input                               NC4_DONE              ,
    input                               NT1_DONE              ,
    input                               NT2_DONE              ,
    input                               NT3_DONE              ,
    input                               NT4_DONE

    ) ;

// =================================================================================================
// Defination of Internal Signals
// =================================================================================================

    //---------------------------------------------------------------------
    // Defination of Parameter
    //---------------------------------------------------------------------

    parameter                           P_CTRL_REGISTER          =  18'h0000     ;
    parameter                           P_STATUS_REGISTER        =  18'h0004     ;
    parameter                           P_NC1_SEND_NUM           =  18'h0008     ;
    parameter                           P_NC2_SEND_NUM           =  18'h000C     ;
    parameter                           P_NC3_SEND_NUM           =  18'h0010     ;
    parameter                           P_NC4_SEND_NUM           =  18'h0014     ;
    parameter                           P_NT1_SEND_NUM           =  18'h0018     ;
    parameter                           P_NT2_SEND_NUM           =  18'h001C     ;
    parameter                           P_NT3_SEND_NUM           =  18'h0020     ;
    parameter                           P_NT4_SEND_NUM           =  18'h0024     ;
    parameter                           P_WD_FIFO1_WR_NUM        =  18'h0028     ;
    parameter                           P_WD_FIFO2_WR_NUM        =  18'h002C     ;
    parameter                           P_RC_FIFO1_WR_NUM        =  18'h0030     ;
    parameter                           P_RC_FIFO2_WR_NUM        =  18'h0034     ;
    parameter                           P_RD_FIFO1_WR_NUM        =  18'h0038     ;
    parameter                           P_RD_FIFO2_WR_NUM        =  18'h003C     ;

    parameter                           P_FIFO1_WRITE_REGISTER   =  18'h1000     ;
    parameter                           P_FIFO1_SEND_RAM_WRITE   =  18'h1004     ;
    parameter                           P_FIFO2_WRITE_REGISTER   =  18'h2000     ;
    parameter                           P_FIFO2_SEND_RAM_WRITE   =  18'h2004     ;
    parameter                           P_DATA_READ_REGISTER     =  18'h3000     ;

    parameter                           P_JLK_RESET_REGISTER     =  18'h4000     ;
    parameter                           P_FIFO_SELECT_REGISTER   =  18'h4004     ;
    parameter                           P_CLK_FREQ_SEL_REGISTER  =  18'h4008     ;

    parameter                           P_FIFO_RESET_REGISTER    =  18'h5000     ;

    parameter                           P_DEBUG_REGISTER         =  18'hF000     ;

    //---------------------------------------------------------------------
    // Defination of Internal Signals
    //---------------------------------------------------------------------

    // fifo sel
    reg              [ 1:0]             r_fifo1_wr_sel          ;
    reg              [ 1:0]             r_fifo1_rd_sel          ;
    reg              [ 1:0]             r_fifo2_wr_sel          ;
    reg              [ 1:0]             r_fifo2_rd_sel          ;

    // jlk emif
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_jlk_reset_n           ;
    wire                                s_strbd                 ;
    reg                                 r_strbd_d1              ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_strbd_d2              ;
    reg                                 r_mem_access            ;
    reg              [ 3:0]             r_clk_freq_sel          ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire             [15:0]             s_jlk_emif_data_in      ;

    // dsp emif
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [31:0]             r_nc1_send_num          ;
    reg              [31:0]             r_nc2_send_num          ;
    reg              [31:0]             r_nc3_send_num          ;
    reg              [31:0]             r_nc4_send_num          ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [ 8:0]             r_nt1_send_num          ;
    reg              [ 8:0]             r_nt2_send_num          ;
    reg              [ 8:0]             r_nt3_send_num          ;
    reg              [ 8:0]             r_nt4_send_num          ;

    reg                                 r_nc1_tx_req            ;
    reg                                 r_nc2_tx_req            ;
    reg                                 r_nc3_tx_req            ;
    reg                                 r_nc4_tx_req            ;
    reg                                 r_nt1_tx_req            ;
    reg                                 r_nt2_tx_req            ;
    reg                                 r_nt3_tx_req            ;
    reg                                 r_nt4_tx_req            ;

    reg                                 r_nt1_tx_req_d1         ;
    reg                                 r_nt2_tx_req_d1         ;
    reg                                 r_nt3_tx_req_d1         ;
    reg                                 r_nt4_tx_req_d1         ;
    wire                                s_nt1_tx_req_pos        ;
    wire                                s_nt2_tx_req_pos        ;
    wire                                s_nt3_tx_req_pos        ;
    wire                                s_nt4_tx_req_pos        ;

    reg                                 r_wc_fifo1_wr_en        ;
    reg                                 r_wc_fifo2_wr_en        ;
    reg              [33:0]             r_wc_fifo1_din          ;
    reg              [33:0]             r_wc_fifo2_din          ;

    reg                                 r_wd_fifo1_wr_en        ;
    reg                                 r_wd_fifo2_wr_en        ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [15:0]             r_wd_fifo1_din          ;
    reg              [15:0]             r_wd_fifo2_din          ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_wc_fifo1_wr_en_d1     ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [33:0]             r_wc_fifo1_din_d1       ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_wd_fifo1_wr_en_d1     ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [15:0]             r_wd_fifo1_din_d1       ;
    reg                                 r_wc_fifo2_wr_en_d1     ;
    reg              [33:0]             r_wc_fifo2_din_d1       ;
    reg                                 r_wd_fifo2_wr_en_d1     ;
    reg              [15:0]             r_wd_fifo2_din_d1       ;

(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [23:0]             r_status                ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [15:0]             r_ctrl_register         ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [15:0]             r_debug_register        ;

    reg                                 r_nc1_rd_req            ;
    reg                                 r_nc2_rd_req            ;
    reg                                 r_nc3_rd_req            ;
    reg                                 r_nc4_rd_req            ;
    reg                                 r_nt1_rd_req            ;
    reg                                 r_nt2_rd_req            ;
    reg                                 r_nt3_rd_req            ;
    reg                                 r_nt4_rd_req            ;

    reg                                 r_nc1_rd_req_d1         ;
    reg                                 r_nc2_rd_req_d1         ;
    reg                                 r_nc3_rd_req_d1         ;
    reg                                 r_nc4_rd_req_d1         ;
    reg                                 r_nt1_rd_req_d1         ;
    reg                                 r_nt2_rd_req_d1         ;
    reg                                 r_nt3_rd_req_d1         ;
    reg                                 r_nt4_rd_req_d1         ;

    wire                                s_nc1_rd_req_neg        ;
    wire                                s_nc2_rd_req_neg        ;
    wire                                s_nc3_rd_req_neg        ;
    wire                                s_nc4_rd_req_neg        ;
    wire                                s_nt1_rd_req_neg        ;
    wire                                s_nt2_rd_req_neg        ;
    wire                                s_nt3_rd_req_neg        ;
    wire                                s_nt4_rd_req_neg        ;

    reg                                 r_rc_fifo1_rd_en        ;
    reg                                 r_rc_fifo2_rd_en        ;

    reg                                 r_rd_fifo1_rd_en        ;
    reg                                 r_rd_fifo2_rd_en        ;

    reg                                 r_fifo_rst              ;
    reg              [31:0]             r_fifo_rst_sft          ;

    reg              [31:0]             r_emif_read_data        ;

    reg                                 r_smartnc1_err_d1       ;
    reg                                 r_smartnc2_err_d1       ;
    reg                                 r_smartnc3_err_d1       ;
    reg                                 r_smartnc4_err_d1       ;
    reg                                 r_smartnt1_err_d1       ;
    reg                                 r_smartnt2_err_d1       ;
    reg                                 r_smartnt3_err_d1       ;
    reg                                 r_smartnt4_err_d1       ;
    reg                                 r_smartnc1_err_d2       ;
    reg                                 r_smartnc2_err_d2       ;
    reg                                 r_smartnc3_err_d2       ;
    reg                                 r_smartnc4_err_d2       ;
    reg                                 r_smartnt1_err_d2       ;
    reg                                 r_smartnt2_err_d2       ;
    reg                                 r_smartnt3_err_d2       ;
    reg                                 r_smartnt4_err_d2       ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_smartnc1_err_flag     ;
    reg                                 r_smartnc2_err_flag     ;
    reg                                 r_smartnc3_err_flag     ;
    reg                                 r_smartnc4_err_flag     ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_smartnt1_err_flag     ;
    reg                                 r_smartnt2_err_flag     ;
    reg                                 r_smartnt3_err_flag     ;
    reg                                 r_smartnt4_err_flag     ;

    reg                                 r_fifo1_send_ram_write_ena ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg                                 r_fifo1_send_ram_write_ena_d1 ;
    reg                                 r_fifo1_send_ram_wea    ;
    reg                                 r_fifo1_send_ram_wea_d1 ;
    wire                                r_fifo1_send_ram_wea_neg;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    reg              [ 7:0]             r_fifo1_send_ram_write_addr ;

    reg                                 r_fifo2_send_ram_write_ena ;
    reg                                 r_fifo2_send_ram_write_ena_d1 ;
    reg                                 r_fifo2_send_ram_wea    ;
    reg                                 r_fifo2_send_ram_wea_d1 ;
    wire                                r_fifo2_send_ram_wea_neg;
    reg              [ 7:0]             r_fifo2_send_ram_write_addr ;

    // for debug
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire             [13:0]             s_wd_fifo1_wr_data_cnt  ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire                                s_rd_fifo1_rd_en        ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire             [15:0]             s_rd_fifo1_dout         ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire             [13:0]             s_rd_fifo1_wr_data_cnt  ;
(*KEEP = "TRUE" ,MARK_DEBUG = "TRUE" *)    wire                                s_rd_fifo1_empty        ;

// =================================================================================================
// RTL body
// =================================================================================================

    // for debug
    assign s_rd_fifo1_rd_en = RD_FIFO1_RD_EN ;
    assign s_rd_fifo1_dout  = RD_FIFO1_DOUT  ;
    assign s_rd_fifo1_wr_data_cnt = RD_FIFO1_WR_DATA_CNT ;
    assign s_rd_fifo1_empty = RD_FIFO1_EMPTY ;
    assign s_wd_fifo1_wr_data_cnt = WD_FIFO1_WR_DATA_CNT ;

    //-----------------------------------------------
    // FIFO1 SEND RAM WTIRE
    //-----------------------------------------------
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_fifo1_send_ram_write_ena  <= 1'b0  ;
            r_fifo1_send_ram_wea        <= 1'b0  ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_FIFO1_SEND_RAM_WRITE) ) begin
                r_fifo1_send_ram_write_ena  <= 1'b1 ;
                r_fifo1_send_ram_wea        <= 1'b1 ;
            end else begin
                r_fifo1_send_ram_write_ena  <= 1'b0  ;
                r_fifo1_send_ram_wea        <= 1'b0  ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_fifo1_send_ram_wea_d1 <= 1'b0 ;
            r_fifo1_send_ram_write_ena_d1 <= 1'b0 ;
        end else begin
            r_fifo1_send_ram_wea_d1 <= r_fifo1_send_ram_wea ;
            r_fifo1_send_ram_write_ena_d1 <= r_fifo1_send_ram_write_ena ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_fifo1_send_ram_write_addr <= 8'b0 ;
        end else begin
            if ( s_nt1_tx_req_pos | s_nt2_tx_req_pos ) begin
                r_fifo1_send_ram_write_addr <= 8'b0 ;
            end else if ( r_fifo1_send_ram_wea_neg ) begin
                r_fifo1_send_ram_write_addr <= r_fifo1_send_ram_write_addr + 1'b1 ;
            end
        end
    end

    assign r_fifo1_send_ram_wea_neg  = ~r_fifo1_send_ram_wea & r_fifo1_send_ram_wea_d1 ;
    assign FIFO1_SEND_RAM_WRITE_ENA  = r_fifo1_send_ram_write_ena_d1  ;
    assign FIFO1_SEND_RAM_WEA        = r_fifo1_send_ram_wea | r_fifo1_send_ram_wea_d1  ;
    assign FIFO1_SEND_RAM_WRITE_ADDR = r_fifo1_send_ram_write_addr ;
    assign FIFO1_SEND_RAM_WRITE_DATA = r_wd_fifo1_din           ;

    //-----------------------------------------------
    // FIFO2 SEND RAM WTIRE
    //-----------------------------------------------
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_fifo2_send_ram_write_ena  <= 1'b0  ;
            r_fifo2_send_ram_wea        <= 1'b0  ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_FIFO2_SEND_RAM_WRITE) ) begin
                r_fifo2_send_ram_write_ena  <= 1'b1 ;
                r_fifo2_send_ram_wea        <= 1'b1 ;
            end else begin
                r_fifo2_send_ram_write_ena  <= 1'b0  ;
                r_fifo2_send_ram_wea        <= 1'b0  ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_fifo2_send_ram_wea_d1 <= 1'b0 ;
            r_fifo2_send_ram_write_ena_d1 <= 1'b0 ;
        end else begin
            r_fifo2_send_ram_wea_d1 <= r_fifo2_send_ram_wea ;
            r_fifo2_send_ram_write_ena_d1 <= r_fifo2_send_ram_write_ena ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_fifo2_send_ram_write_addr <= 8'b0 ;
        end else begin
            if ( s_nt3_tx_req_pos | s_nt4_tx_req_pos ) begin
                r_fifo2_send_ram_write_addr <= 8'b0 ;
            end else if ( r_fifo1_send_ram_wea_neg ) begin
                r_fifo2_send_ram_write_addr <= r_fifo2_send_ram_write_addr + 1'b1 ;
            end
        end
    end

    assign r_fifo2_send_ram_wea_neg  = ~r_fifo2_send_ram_wea & r_fifo2_send_ram_wea_d1 ;
    assign FIFO2_SEND_RAM_WRITE_ENA  = r_fifo2_send_ram_write_ena_d1  ;
    assign FIFO2_SEND_RAM_WEA        = r_fifo2_send_ram_wea | r_fifo2_send_ram_wea_d1  ;
    assign FIFO2_SEND_RAM_WRITE_ADDR = r_fifo2_send_ram_write_addr ;
    assign FIFO2_SEND_RAM_WRITE_DATA = r_wd_fifo2_din_d1 ;

    //-----------------------------------------------
    // FIFO SEL
    //-----------------------------------------------
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_fifo1_wr_sel <= 2'b00  ; // default smartnc1
            r_fifo1_rd_sel <= 2'b10  ; // default smartnt1
            r_fifo2_wr_sel <= 2'b00  ; // default smartnc3
            r_fifo2_rd_sel <= 2'b11  ; // default smartnt4
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_FIFO_SELECT_REGISTER) ) begin
                r_fifo1_wr_sel <= EMIF_ED_IN[1:0]  ;
                r_fifo1_rd_sel <= EMIF_ED_IN[3:2]  ;
                r_fifo2_wr_sel <= EMIF_ED_IN[5:4]  ;
                r_fifo2_rd_sel <= EMIF_ED_IN[7:6]  ;
            end
        end
    end

    assign FIFO1_WR_SEL_0 = r_fifo1_wr_sel[0] ;
    assign FIFO1_WR_SEL_1 = r_fifo1_wr_sel[1] ;
    assign FIFO1_RD_SEL_0 = r_fifo1_rd_sel[0] ;
    assign FIFO1_RD_SEL_1 = r_fifo1_rd_sel[1] ;
    assign FIFO2_WR_SEL_0 = r_fifo2_wr_sel[0] ;
    assign FIFO2_WR_SEL_1 = r_fifo2_wr_sel[1] ;
    assign FIFO2_RD_SEL_0 = r_fifo2_rd_sel[0] ;
    assign FIFO2_RD_SEL_1 = r_fifo2_rd_sel[1] ;

    //-----------------------------------------------
    // JLK EMIF
    //-----------------------------------------------
    assign I_RESET_N            = r_jlk_reset_n         ;
    assign I_CPU_ADDR           = EMIF_EA[17:0]         ;
    assign s_jlk_emif_data_in   = IO_CPU_DQ             ;
    assign IO_CPU_DQ            = ( I_RD_ACCESS ) ? 16'hzzzz : EMIF_ED_IN[15:0] ;
    assign I_SELECT_N           = EMIF_CE_N[2]          ;
    assign s_strbd              = EMIF_WE_N & EMIF_RE_N ;
    assign I_STRBD_N            = r_strbd_d2            ;
    assign I_MEM_ACCESS         = EMIF_EA[18]           ;
    assign I_RD_ACCESS          = ~EMIF_OE_N            ;
    assign I_GC_MODE            = 3'b001                ;
    assign I_CLK_FREQ_SEL       = r_clk_freq_sel        ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_jlk_reset_n <= 1'b1  ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_JLK_RESET_REGISTER) ) begin
                r_jlk_reset_n <= EMIF_ED_IN[0]  ;
            end else begin
                r_jlk_reset_n <= r_jlk_reset_n ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_strbd_d1 <= 1'b1  ;
            r_strbd_d2 <= 1'b1  ;
        end else begin
            r_strbd_d1 <= s_strbd    ;
            r_strbd_d2 <= r_strbd_d1 ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_clk_freq_sel <= 4'b0101  ; // default 2.5G
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CLK_FREQ_SEL_REGISTER) ) begin
                r_clk_freq_sel <= EMIF_ED_IN[3:0]  ;
            end else begin
                r_clk_freq_sel <= r_clk_freq_sel   ;
            end
        end
    end

    //-----------------------------------------------
    // FIFO WR
    //-----------------------------------------------
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nc1_send_num  <= 32'b0 ;
            r_nc2_send_num  <= 32'b0 ;
            r_nc3_send_num  <= 32'b0 ;
            r_nc4_send_num  <= 32'b0 ;
            r_nt1_send_num  <= 9'b0  ;
            r_nt2_send_num  <= 9'b0  ;
            r_nt3_send_num  <= 9'b0  ;
            r_nt4_send_num  <= 9'b0  ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_NC1_SEND_NUM)) r_nc1_send_num  <= EMIF_ED_IN ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_NC2_SEND_NUM)) r_nc2_send_num  <= EMIF_ED_IN ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_NC3_SEND_NUM)) r_nc3_send_num  <= EMIF_ED_IN ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_NC4_SEND_NUM)) r_nc4_send_num  <= EMIF_ED_IN ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_NT1_SEND_NUM)) r_nt1_send_num  <= EMIF_ED_IN[8:0] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_NT2_SEND_NUM)) r_nt2_send_num  <= EMIF_ED_IN[8:0] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_NT3_SEND_NUM)) r_nt3_send_num  <= EMIF_ED_IN[8:0] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_NT4_SEND_NUM)) r_nt4_send_num  <= EMIF_ED_IN[8:0] ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nc1_tx_req <= 1'b0 ;
            r_nc2_tx_req <= 1'b0 ;
            r_nc3_tx_req <= 1'b0 ;
            r_nc4_tx_req <= 1'b0 ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) && (EMIF_ED_IN[0] == 1'b1) ) r_nc1_tx_req <= 1'b1 ; else r_nc1_tx_req <= 1'b0 ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) && (EMIF_ED_IN[1] == 1'b1) ) r_nc2_tx_req <= 1'b1 ; else r_nc2_tx_req <= 1'b0 ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) && (EMIF_ED_IN[2] == 1'b1) ) r_nc3_tx_req <= 1'b1 ; else r_nc3_tx_req <= 1'b0 ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) && (EMIF_ED_IN[3] == 1'b1) ) r_nc4_tx_req <= 1'b1 ; else r_nc4_tx_req <= 1'b0 ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nt1_tx_req <= 1'b0 ;
            r_nt2_tx_req <= 1'b0 ;
            r_nt3_tx_req <= 1'b0 ;
            r_nt4_tx_req <= 1'b0 ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nt1_tx_req <= EMIF_ED_IN[4] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nt2_tx_req <= EMIF_ED_IN[5] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nt3_tx_req <= EMIF_ED_IN[6] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nt4_tx_req <= EMIF_ED_IN[7] ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nt1_tx_req_d1 <= 1'b0 ;
            r_nt2_tx_req_d1 <= 1'b0 ;
            r_nt3_tx_req_d1 <= 1'b0 ;
            r_nt4_tx_req_d1 <= 1'b0 ;
        end else begin
            r_nt1_tx_req_d1 <= r_nt1_tx_req ;
            r_nt2_tx_req_d1 <= r_nt2_tx_req ;
            r_nt3_tx_req_d1 <= r_nt3_tx_req ;
            r_nt4_tx_req_d1 <= r_nt4_tx_req ;
        end
    end

    assign s_nt1_tx_req_pos = ~r_nt1_tx_req_d1 & r_nt1_tx_req ;
    assign s_nt2_tx_req_pos = ~r_nt2_tx_req_d1 & r_nt2_tx_req ;
    assign s_nt3_tx_req_pos = ~r_nt3_tx_req_d1 & r_nt3_tx_req ;
    assign s_nt4_tx_req_pos = ~r_nt4_tx_req_d1 & r_nt4_tx_req ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wc_fifo1_wr_en <= 1'b0 ;
        end else begin
            r_wc_fifo1_wr_en <= r_nc1_tx_req | r_nc2_tx_req ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wc_fifo2_wr_en <= 1'b0 ;
        end else begin
            r_wc_fifo2_wr_en <= r_nc3_tx_req | r_nc4_tx_req ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wc_fifo1_din <= 34'b0 ;
            r_wc_fifo2_din <= 34'b0 ;
        end else begin
            if( r_nc1_tx_req ) begin
                r_wc_fifo1_din <= { 2'b00 , r_nc1_send_num } ;
            end else if( r_nc2_tx_req ) begin
                r_wc_fifo1_din <= { 2'b01 , r_nc2_send_num } ;
            end

            if( r_nc3_tx_req ) begin
                r_wc_fifo2_din <= { 2'b00 , r_nc3_send_num } ;
            end else if( r_nc4_tx_req ) begin
                r_wc_fifo2_din <= { 2'b01 , r_nc4_send_num } ;
            end
        end
    end

    assign NT1_SEND_FLAG  = r_nt1_tx_req ;
    assign NT2_SEND_FLAG  = r_nt2_tx_req ;
    assign NT3_SEND_FLAG  = r_nt3_tx_req ;
    assign NT4_SEND_FLAG  = r_nt4_tx_req ;

    assign NT1_SEND_NUM = ( r_nt1_tx_req ) ? r_nt1_send_num : 9'b0 ;
    assign NT2_SEND_NUM = ( r_nt2_tx_req ) ? r_nt2_send_num : 9'b0 ;
    assign NT3_SEND_NUM = ( r_nt3_tx_req ) ? r_nt3_send_num : 9'b0 ;
    assign NT4_SEND_NUM = ( r_nt4_tx_req ) ? r_nt4_send_num : 9'b0 ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wd_fifo1_wr_en <= 1'b0  ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_FIFO1_WRITE_REGISTER) ) begin
                r_wd_fifo1_wr_en <= 1'b1 ;
            end else begin
                r_wd_fifo1_wr_en <= 1'b0 ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wd_fifo2_wr_en <= 1'b0  ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_FIFO2_WRITE_REGISTER) ) begin
                r_wd_fifo2_wr_en <= 1'b1 ;
            end else begin
                r_wd_fifo2_wr_en <= 1'b0 ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wd_fifo1_din <= 16'b0     ;
            r_wd_fifo2_din <= 16'b0     ;
        end else begin
            r_wd_fifo1_din <= EMIF_ED_IN[15:0] ;
            r_wd_fifo2_din <= EMIF_ED_IN[15:0] ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_wc_fifo1_wr_en_d1  <= 1'b0     ;
            r_wc_fifo1_din_d1    <= 34'b0    ;
            r_wd_fifo1_wr_en_d1  <= 1'b0     ;
            r_wd_fifo1_din_d1    <= 16'b0    ;
            r_wc_fifo2_wr_en_d1  <= 1'b0     ;
            r_wc_fifo2_din_d1    <= 34'b0    ;
            r_wd_fifo2_wr_en_d1  <= 1'b0     ;
            r_wd_fifo2_din_d1    <= 16'b0    ;
        end else begin
            r_wc_fifo1_wr_en_d1  <= r_wc_fifo1_wr_en    ;
            r_wc_fifo1_din_d1    <= r_wc_fifo1_din      ;
            r_wd_fifo1_wr_en_d1  <= r_wd_fifo1_wr_en    ;
            r_wd_fifo1_din_d1    <= r_wd_fifo1_din      ;
            r_wc_fifo2_wr_en_d1  <= r_wc_fifo2_wr_en    ;
            r_wc_fifo2_din_d1    <= r_wc_fifo2_din      ;
            r_wd_fifo2_wr_en_d1  <= r_wd_fifo2_wr_en    ;
            r_wd_fifo2_din_d1    <= r_wd_fifo2_din      ;
        end
    end

    assign WC_FIFO1_WR_EN = r_wc_fifo1_wr_en_d1 ;
    assign WC_FIFO1_DIN   = r_wc_fifo1_din_d1   ;

    assign WD_FIFO1_WR_EN = r_wd_fifo1_wr_en_d1 ;
    assign WD_FIFO1_DIN   = r_wd_fifo1_din_d1   ;

    assign WC_FIFO2_WR_EN = r_wc_fifo2_wr_en_d1 ;
    assign WC_FIFO2_DIN   = r_wc_fifo2_din_d1   ;

    assign WD_FIFO2_WR_EN = r_wd_fifo2_wr_en_d1 ;
    assign WD_FIFO2_DIN   = r_wd_fifo2_din_d1   ;

    //-----------------------------------------------
    // FIFO RESET
    //-----------------------------------------------
    always @( posedge SYS_CLK or negedge RST_N ) begin
        if( !RST_N ) begin
            r_fifo_rst_sft <= {32{1'b0}} ;
        end else begin
            if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_FIFO_RESET_REGISTER) && (EMIF_ED_IN[0] == 1'b1) ) begin
                r_fifo_rst_sft <= {32{1'b1}} ;
            end else begin
                r_fifo_rst_sft <= {r_fifo_rst_sft[30:0],1'b0} ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if( !RST_N ) begin
            r_fifo_rst <= 1'b0 ;
        end else begin
            r_fifo_rst <= r_fifo_rst_sft[31] ;
        end
    end

    assign FIFO_RST = r_fifo_rst ;

    //-----------------------------------------------
    // FIFO RD
    //-----------------------------------------------
    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_status[7:0] <= 8'b0 ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) ) begin
                if ( EMIF_ED_IN[0] == 1'b1 ) r_status[0] <= 1'b0 ;
                if ( EMIF_ED_IN[1] == 1'b1 ) r_status[1] <= 1'b0 ;
                if ( EMIF_ED_IN[2] == 1'b1 ) r_status[2] <= 1'b0 ;
                if ( EMIF_ED_IN[3] == 1'b1 ) r_status[3] <= 1'b0 ;
                if ( EMIF_ED_IN[4] == 1'b1 ) r_status[4] <= 1'b0 ;
                if ( EMIF_ED_IN[5] == 1'b1 ) r_status[5] <= 1'b0 ;
                if ( EMIF_ED_IN[6] == 1'b1 ) r_status[6] <= 1'b0 ;
                if ( EMIF_ED_IN[7] == 1'b1 ) r_status[7] <= 1'b0 ;
            end else begin
                if ( NC1_DONE == 1'b1 ) r_status[0] <= 1'b1 ;
                if ( NC2_DONE == 1'b1 ) r_status[1] <= 1'b1 ;
                if ( NC3_DONE == 1'b1 ) r_status[2] <= 1'b1 ;
                if ( NC4_DONE == 1'b1 ) r_status[3] <= 1'b1 ;
                if ( NT1_DONE == 1'b1 ) r_status[4] <= 1'b1 ;
                if ( NT2_DONE == 1'b1 ) r_status[5] <= 1'b1 ;
                if ( NT3_DONE == 1'b1 ) r_status[6] <= 1'b1 ;
                if ( NT4_DONE == 1'b1 ) r_status[7] <= 1'b1 ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_status[15:8] <= 8'b0 ;
        end else begin
            if ( RC_FIFO1_EMPTY == 1'b0 && RC_FIFO1_DOUT[33:32] == 2'b00 ) r_status[8]  <= 1'b1 ; else r_status[8]  <= 1'b0 ;
            if ( RC_FIFO1_EMPTY == 1'b0 && RC_FIFO1_DOUT[33:32] == 2'b01 ) r_status[9]  <= 1'b1 ; else r_status[9]  <= 1'b0 ;
            if ( RC_FIFO2_EMPTY == 1'b0 && RC_FIFO2_DOUT[33:32] == 2'b00 ) r_status[10] <= 1'b1 ; else r_status[10] <= 1'b0 ;
            if ( RC_FIFO2_EMPTY == 1'b0 && RC_FIFO2_DOUT[33:32] == 2'b01 ) r_status[11] <= 1'b1 ; else r_status[11] <= 1'b0 ;
            if ( RC_FIFO1_EMPTY == 1'b0 && RC_FIFO1_DOUT[33:32] == 2'b10 ) r_status[12] <= 1'b1 ; else r_status[12] <= 1'b0 ;
            if ( RC_FIFO1_EMPTY == 1'b0 && RC_FIFO1_DOUT[33:32] == 2'b11 ) r_status[13] <= 1'b1 ; else r_status[13] <= 1'b0 ;
            if ( RC_FIFO2_EMPTY == 1'b0 && RC_FIFO2_DOUT[33:32] == 2'b10 ) r_status[14] <= 1'b1 ; else r_status[14] <= 1'b0 ;
            if ( RC_FIFO2_EMPTY == 1'b0 && RC_FIFO2_DOUT[33:32] == 2'b11 ) r_status[15] <= 1'b1 ; else r_status[15] <= 1'b0 ;
        end
    end

    // smart error signale cross clock region
    always @( posedge SYS_CLK or posedge RST_N ) begin
        if( !RST_N ) begin
            r_smartnc1_err_d1 <= 1'b0 ;
            r_smartnc2_err_d1 <= 1'b0 ;
            r_smartnc3_err_d1 <= 1'b0 ;
            r_smartnc4_err_d1 <= 1'b0 ;
            r_smartnt1_err_d1 <= 1'b0 ;
            r_smartnt2_err_d1 <= 1'b0 ;
            r_smartnt3_err_d1 <= 1'b0 ;
            r_smartnt4_err_d1 <= 1'b0 ;
            r_smartnc1_err_d2 <= 1'b0 ;
            r_smartnc2_err_d2 <= 1'b0 ;
            r_smartnc3_err_d2 <= 1'b0 ;
            r_smartnc4_err_d2 <= 1'b0 ;
            r_smartnt1_err_d2 <= 1'b0 ;
            r_smartnt2_err_d2 <= 1'b0 ;
            r_smartnt3_err_d2 <= 1'b0 ;
            r_smartnt4_err_d2 <= 1'b0 ;
        end else begin
            r_smartnc1_err_d1 <= SMARTNC1_ERR ;
            r_smartnc2_err_d1 <= SMARTNC2_ERR ;
            r_smartnc3_err_d1 <= SMARTNC3_ERR ;
            r_smartnc4_err_d1 <= SMARTNC4_ERR ;
            r_smartnt1_err_d1 <= SMARTNT1_ERR ;
            r_smartnt2_err_d1 <= SMARTNT2_ERR ;
            r_smartnt3_err_d1 <= SMARTNT3_ERR ;
            r_smartnt4_err_d1 <= SMARTNT4_ERR ;
            r_smartnc1_err_d2 <= r_smartnc1_err_d1 ;
            r_smartnc2_err_d2 <= r_smartnc2_err_d1 ;
            r_smartnc3_err_d2 <= r_smartnc3_err_d1 ;
            r_smartnc4_err_d2 <= r_smartnc4_err_d1 ;
            r_smartnt1_err_d2 <= r_smartnt1_err_d1 ;
            r_smartnt2_err_d2 <= r_smartnt2_err_d1 ;
            r_smartnt3_err_d2 <= r_smartnt3_err_d1 ;
            r_smartnt4_err_d2 <= r_smartnt4_err_d1 ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_smartnc1_err_flag <= 1'b0 ;
            r_smartnc2_err_flag <= 1'b0 ;
            r_smartnc3_err_flag <= 1'b0 ;
            r_smartnc4_err_flag <= 1'b0 ;
            r_smartnt1_err_flag <= 1'b0 ;
            r_smartnt2_err_flag <= 1'b0 ;
            r_smartnt3_err_flag <= 1'b0 ;
            r_smartnt4_err_flag <= 1'b0 ;
        end else begin
            if( r_smartnc1_err_d1 & ~r_smartnc1_err_d2 ) begin
                r_smartnc1_err_flag <= 1'b1 ;
            end else if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) && EMIF_ED_IN[16] == 1'b1 ) begin
                r_smartnc1_err_flag <= 1'b0 ;
            end

            if( r_smartnc2_err_d1 & ~r_smartnc2_err_d2 ) begin
                r_smartnc2_err_flag <= 1'b1 ;
            end else if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) && EMIF_ED_IN[17] == 1'b1 ) begin
                r_smartnc2_err_flag <= 1'b0 ;
            end

            if( r_smartnc3_err_d1 & ~r_smartnc3_err_d2 ) begin
                r_smartnc3_err_flag <= 1'b1 ;
            end else if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) && EMIF_ED_IN[18] == 1'b1 ) begin
                r_smartnc3_err_flag <= 1'b0 ;
            end

            if( r_smartnc4_err_d1 & ~r_smartnc4_err_d2 ) begin
                r_smartnc4_err_flag <= 1'b1 ;
            end else if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) && EMIF_ED_IN[19] == 1'b1 ) begin
                r_smartnc4_err_flag <= 1'b0 ;
            end

            if( r_smartnt1_err_d1 & ~r_smartnt1_err_d2 ) begin
                r_smartnt1_err_flag <= 1'b1 ;
            end else if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) && EMIF_ED_IN[20] == 1'b1 ) begin
                r_smartnt1_err_flag <= 1'b0 ;
            end

            if( r_smartnt2_err_d1 & ~r_smartnt2_err_d2 ) begin
                r_smartnt2_err_flag <= 1'b1 ;
            end else if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) && EMIF_ED_IN[21] == 1'b1 ) begin
                r_smartnt2_err_flag <= 1'b0 ;
            end

            if( r_smartnt3_err_d1 & ~r_smartnt3_err_d2 ) begin
                r_smartnt3_err_flag <= 1'b1 ;
            end else if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) && EMIF_ED_IN[22] == 1'b1 ) begin
                r_smartnt3_err_flag <= 1'b0 ;
            end

            if( r_smartnt4_err_d1 & ~r_smartnt4_err_d2 ) begin
                r_smartnt4_err_flag <= 1'b1 ;
            end else if( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) && EMIF_ED_IN[23] == 1'b1 ) begin
                r_smartnt4_err_flag <= 1'b0 ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_status[23:16] <= 8'b0 ;
        end else begin
            r_status[16] <= r_smartnc1_err_flag ;
            r_status[17] <= r_smartnc2_err_flag ;
            r_status[18] <= r_smartnc3_err_flag ;
            r_status[19] <= r_smartnc4_err_flag ;
            r_status[20] <= r_smartnt1_err_flag ;
            r_status[21] <= r_smartnt2_err_flag ;
            r_status[22] <= r_smartnt3_err_flag ;
            r_status[23] <= r_smartnt4_err_flag ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_ctrl_register <= 16'b0 ;
        end else begin
            r_ctrl_register[0]  <= r_nc1_tx_req ;
            r_ctrl_register[1]  <= r_nc2_tx_req ;
            r_ctrl_register[2]  <= r_nc3_tx_req ;
            r_ctrl_register[3]  <= r_nc4_tx_req ;
            r_ctrl_register[4]  <= r_nt1_tx_req ;
            r_ctrl_register[5]  <= r_nt2_tx_req ;
            r_ctrl_register[6]  <= r_nt3_tx_req ;
            r_ctrl_register[7]  <= r_nt4_tx_req ;
            r_ctrl_register[8]  <= r_nc1_rd_req ;
            r_ctrl_register[9]  <= r_nc2_rd_req ;
            r_ctrl_register[10] <= r_nc3_rd_req ;
            r_ctrl_register[11] <= r_nc4_rd_req ;
            r_ctrl_register[12] <= r_nt1_rd_req ;
            r_ctrl_register[13] <= r_nt2_rd_req ;
            r_ctrl_register[14] <= r_nt3_rd_req ;
            r_ctrl_register[15] <= r_nt4_rd_req ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_debug_register <= 16'b0 ;
        end else begin
            r_debug_register[0]  <= WC_FIFO1_UNDERFLOW ;
            r_debug_register[1]  <= WC_FIFO1_OVERFLOW  ;
            r_debug_register[2]  <= WD_FIFO1_UNDERFLOW ;
            r_debug_register[3]  <= WD_FIFO1_OVERFLOW  ;
            r_debug_register[4]  <= RC_FIFO1_UNDERFLOW ;
            r_debug_register[5]  <= RC_FIFO1_OVERFLOW  ;
            r_debug_register[6]  <= RD_FIFO1_UNDERFLOW ;
            r_debug_register[7]  <= RD_FIFO1_OVERFLOW  ;
            r_debug_register[8]  <= WC_FIFO2_UNDERFLOW ;
            r_debug_register[9]  <= WC_FIFO2_OVERFLOW  ;
            r_debug_register[10] <= WD_FIFO2_UNDERFLOW ;
            r_debug_register[11] <= WD_FIFO2_OVERFLOW  ;
            r_debug_register[12] <= RC_FIFO2_UNDERFLOW ;
            r_debug_register[13] <= RC_FIFO2_OVERFLOW  ;
            r_debug_register[14] <= RD_FIFO2_UNDERFLOW ;
            r_debug_register[15] <= RD_FIFO2_OVERFLOW  ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nc1_rd_req <= 1'b0 ;
            r_nc2_rd_req <= 1'b0 ;
            r_nc3_rd_req <= 1'b0 ;
            r_nc4_rd_req <= 1'b0 ;
            r_nt1_rd_req <= 1'b0 ;
            r_nt2_rd_req <= 1'b0 ;
            r_nt3_rd_req <= 1'b0 ;
            r_nt4_rd_req <= 1'b0 ;
        end else begin
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nc1_rd_req <= EMIF_ED_IN[8]  ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nc2_rd_req <= EMIF_ED_IN[9]  ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nc3_rd_req <= EMIF_ED_IN[10] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nc4_rd_req <= EMIF_ED_IN[11] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nt1_rd_req <= EMIF_ED_IN[12] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nt2_rd_req <= EMIF_ED_IN[13] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nt3_rd_req <= EMIF_ED_IN[14] ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_WE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER) ) r_nt4_rd_req <= EMIF_ED_IN[15] ;
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_nc1_rd_req_d1 <= 1'b0 ;
            r_nc2_rd_req_d1 <= 1'b0 ;
            r_nc3_rd_req_d1 <= 1'b0 ;
            r_nc4_rd_req_d1 <= 1'b0 ;
            r_nt1_rd_req_d1 <= 1'b0 ;
            r_nt2_rd_req_d1 <= 1'b0 ;
            r_nt3_rd_req_d1 <= 1'b0 ;
            r_nt4_rd_req_d1 <= 1'b0 ;
        end else begin
            r_nc1_rd_req_d1 <= r_nc1_rd_req ;
            r_nc2_rd_req_d1 <= r_nc2_rd_req ;
            r_nc3_rd_req_d1 <= r_nc3_rd_req ;
            r_nc4_rd_req_d1 <= r_nc4_rd_req ;
            r_nt1_rd_req_d1 <= r_nt1_rd_req ;
            r_nt2_rd_req_d1 <= r_nt2_rd_req ;
            r_nt3_rd_req_d1 <= r_nt3_rd_req ;
            r_nt4_rd_req_d1 <= r_nt4_rd_req ;
        end
    end

    assign s_nc1_rd_req_neg = ~r_nc1_rd_req & r_nc1_rd_req_d1 ;
    assign s_nc2_rd_req_neg = ~r_nc2_rd_req & r_nc2_rd_req_d1 ;
    assign s_nc3_rd_req_neg = ~r_nc3_rd_req & r_nc3_rd_req_d1 ;
    assign s_nc4_rd_req_neg = ~r_nc4_rd_req & r_nc4_rd_req_d1 ;
    assign s_nt1_rd_req_neg = ~r_nt1_rd_req & r_nt1_rd_req_d1 ;
    assign s_nt2_rd_req_neg = ~r_nt2_rd_req & r_nt2_rd_req_d1 ;
    assign s_nt3_rd_req_neg = ~r_nt3_rd_req & r_nt3_rd_req_d1 ;
    assign s_nt4_rd_req_neg = ~r_nt4_rd_req & r_nt4_rd_req_d1 ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rc_fifo1_rd_en <= 1'b0 ;
        end else begin
            if ( s_nc1_rd_req_neg | s_nc2_rd_req_neg | s_nt1_rd_req_neg | s_nt2_rd_req_neg ) begin
                r_rc_fifo1_rd_en <= 1'b1 ;
            end else begin
                r_rc_fifo1_rd_en <= 1'b0 ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rc_fifo2_rd_en <= 1'b0 ;
        end else begin
            if ( s_nc3_rd_req_neg | s_nc4_rd_req_neg | s_nt3_rd_req_neg | s_nt4_rd_req_neg ) begin
                r_rc_fifo2_rd_en <= 1'b1 ;
            end else begin
                r_rc_fifo2_rd_en <= 1'b0 ;
            end
        end
    end

    assign RC_FIFO1_RD_EN = r_rc_fifo1_rd_en ;
    assign RC_FIFO2_RD_EN = r_rc_fifo2_rd_en ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rd_fifo1_rd_en <= 1'b0 ;
        end else begin
            if ( (r_nc1_rd_req == 1'b1) || (r_nc2_rd_req == 1'b1) || (r_nt1_rd_req == 1'b1) || (r_nt2_rd_req == 1'b1) ) begin
                r_rd_fifo1_rd_en <= 1'b1 ;
            end else begin
                r_rd_fifo1_rd_en <= 1'b0 ;
            end
        end
    end

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_rd_fifo2_rd_en <= 1'b0 ;
        end else begin
            if ( (r_nc3_rd_req == 1'b1) || (r_nc4_rd_req == 1'b1) || (r_nt3_rd_req == 1'b1) || (r_nt4_rd_req == 1'b1) ) begin
                r_rd_fifo2_rd_en <= 1'b1 ;
            end else begin
                r_rd_fifo2_rd_en <= 1'b0 ;
            end
        end
    end

    assign RD_FIFO1_RD_EN = ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_DATA_READ_REGISTER) ) ? r_rd_fifo1_rd_en & ~RD_FIFO1_EMPTY : 1'b0 ;
    assign RD_FIFO2_RD_EN = ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_DATA_READ_REGISTER) ) ? r_rd_fifo2_rd_en & ~RD_FIFO2_EMPTY : 1'b0 ;

    always @(posedge SYS_CLK or negedge RST_N) begin
        if (!RST_N) begin
            r_emif_read_data  <= 32'b0 ;
        end else begin
            if ( RD_FIFO1_RD_EN == 1'b1 ) r_emif_read_data <= {16'b0,RD_FIFO1_DOUT}  ;
            if ( RD_FIFO2_RD_EN == 1'b1 ) r_emif_read_data <= {16'b0,RD_FIFO2_DOUT}  ;

            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_CTRL_REGISTER  ) ) r_emif_read_data <= { 16'b0 , r_ctrl_register  }     ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_STATUS_REGISTER) ) r_emif_read_data <= { 8'b0  , r_status         }     ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_DEBUG_REGISTER ) ) r_emif_read_data <= { 16'b0 , r_debug_register }     ;

            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_NC1_SEND_NUM   ) ) r_emif_read_data <= r_nc1_send_num                   ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_NC2_SEND_NUM   ) ) r_emif_read_data <= r_nc2_send_num                   ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_NC3_SEND_NUM   ) ) r_emif_read_data <= r_nc3_send_num                   ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_NC4_SEND_NUM   ) ) r_emif_read_data <= r_nc4_send_num                   ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_NT1_SEND_NUM   ) ) r_emif_read_data <= { 24'b0 , r_nt1_send_num   }     ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_NT2_SEND_NUM   ) ) r_emif_read_data <= { 24'b0 , r_nt2_send_num   }     ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_NT3_SEND_NUM   ) ) r_emif_read_data <= { 24'b0 , r_nt3_send_num   }     ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_NT4_SEND_NUM   ) ) r_emif_read_data <= { 24'b0 , r_nt4_send_num   }     ;

            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_WD_FIFO1_WR_NUM) ) r_emif_read_data <= { 18'b0 , WD_FIFO1_WR_DATA_CNT } ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_WD_FIFO2_WR_NUM) ) r_emif_read_data <= { 18'b0 , WD_FIFO2_WR_DATA_CNT } ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_RC_FIFO1_WR_NUM) ) r_emif_read_data <= { 18'b0 , RC_FIFO1_WR_DATA_CNT } ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_RC_FIFO2_WR_NUM) ) r_emif_read_data <= { 18'b0 , RC_FIFO2_WR_DATA_CNT } ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_RD_FIFO1_WR_NUM) ) r_emif_read_data <= { 18'b0 , RD_FIFO1_WR_DATA_CNT } ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_RD_FIFO2_WR_NUM) ) r_emif_read_data <= { 18'b0 , RD_FIFO2_WR_DATA_CNT } ;

            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_FIFO_SELECT_REGISTER) )  r_emif_read_data <= { 24'b0 , r_fifo2_rd_sel , r_fifo2_wr_sel , r_fifo1_rd_sel , r_fifo1_wr_sel } ;
            if ( (EMIF_CE_N[3] == 1'b0) && (EMIF_OE_N == 1'b0) && (EMIF_EA == P_CLK_FREQ_SEL_REGISTER) ) r_emif_read_data <= { 28'b0 , r_clk_freq_sel } ;

            if ( (EMIF_CE_N[2] == 1'b0) && (EMIF_OE_N == 1'b0) ) r_emif_read_data <= { 16'b0 , s_jlk_emif_data_in } ;
        end
    end

    assign EMIF_ED_OUT = r_emif_read_data ;


endmodule