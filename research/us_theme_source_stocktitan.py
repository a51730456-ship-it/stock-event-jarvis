"""StockTitan에서 받은 **테마별 종목 명부** (2026-08-13 수집).

## 왜 받아 뒀나

지금 앱의 테마 20개는 **내가(Claude가) 손으로 묶은 것**이다. 「빅테크10」처럼
테마가 아닌 것도 섞여 있고, 무엇을 넣고 뺐는지 근거가 없다.
CLAUDE.md 0-1 라 — 명부는 그물과 같은 급이다. 근거가 있어야 한다.

**출처**  https://www.stocktitan.net/stocks/themes  (로그인 없이 전체 공개)
**받은 날** 2026-08-13
**갱신** StockTitan은 분기마다 다시 본다고 적어 두었다.

## affinity 점수 — 이게 이 명부의 값어치다

각 종목에 **테마와 얼마나 붙어 있는지**를 5점 만점으로 매겨 놓았다.

  5점  순수 테마주      양자컴퓨팅의 IONQ·QBTS·RGTI — 이 테마로 먹고사는 회사
  4점  큰 회사의 사업부   양자컴퓨팅의 IBM·GOOGL·MSFT — 연구는 하지만 주가는 딴 데서 움직임
  3점  부품·장비 대는 곳
  2점  주변에서 조금 얽힌 곳
  1점  거의 상관없음

**앱에서 쓸 때는 5점만, 또는 4점 이상만 쓴다.** 3점 아래를 넣으면 테마가
흐려진다 — 양자컴퓨팅에 AMZN이 들어오는 식이다.

## 주의

이것도 **오늘 명부**다. 2018년을 재면서 2026년 묶음을 쓰는 것은 그대로다.
다만 2026-08-13 가짜 테마 시험(`us_theme_placebo.py`)에서 아무렇게나 묶으면
100번 중 50번(반반)이 나왔으므로, 오늘 명부를 쓴다는 것만으로 성적이
좋아지지는 않는다는 것은 확인됐다.

바꾸려면 **바꾸고 나서 전부 다시 재야 한다**(CLAUDE.md 0-1 라).
"""

from __future__ import annotations

# 테마 이름: {티커: affinity 점수}
STOCKTITAN: dict[str, dict[str, int]] = {}


def _put(name: str, raw: str) -> None:
    """티커:점수를 쉼표로 끊어 담는다.

    **줄바꿈을 반드시 지운다.** 공백만 지우면 여러 줄로 적은 문자열에서
    각 줄 첫 티커가 "\\nNVDA"가 되어 통째로 빠진다(2026-08-13에 겪었다 —
    NVDA·XOM·RTX·PANW·CCJ·IONQ 열네 개가 조용히 사라졌다).
    """
    STOCKTITAN[name] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        ticker, score = chunk.rsplit(":", 1)
        STOCKTITAN[name][ticker.strip()] = int(score.strip())


_put("인공지능", """
NVDA:5,GOOGL:5,MSFT:5,AMZN:5,MU:5,PLTR:5,ANET:5,MRVL:5,VRT:5,SMCI:5,SOUN:5,
TSM:4,AVGO:4,META:4,AMD:4,ASML:4,ORCL:4,ARM:4,DELL:4,IBM:4,CRM:4,NOW:4,SNOW:4,
ACN:4,APP:4,ADBE:4,COHR:4,LITE:4,ALAB:4,CRWV:4,NBIS:4,CRDO:4,CLS:4,TSEM:4,
LSCC:4,NVTS:4,BBAI:4,ABSI:4,PERF:4,AAPL:3,TSLA:3,AMAT:3,PANW:3,CRWD:3,QCOM:3,
NET:3,CDNS:3,DDOG:3,SNPS:3,NXPI:3,WDAY:3,GEHC:3,UPST:3,PRCT:3,AOSL:3,INDI:3,
OSS:3,LTRN:3,INTC:2,III:2,VLN:2""")

_put("반도체", """
NVDA:5,TSM:5,MU:5,AMD:5,ASML:5,INTC:5,AMAT:5,LRCX:5,ARM:5,KLAC:5,TXN:5,MRVL:5,
ADI:5,SNDK:5,ASX:5,CDNS:5,SNPS:5,MPWR:5,NXPI:5,TER:5,ALAB:5,UMC:5,CRDO:5,
MCHP:5,ON:5,GFS:5,ENTG:5,MTSI:5,SITM:5,ONTO:5,LSCC:5,AMKR:5,NVMI:5,RMBS:5,
SWKS:5,QRVO:5,CAMT:5,SIMO:5,CRUS:5,ACLS:5,NVTS:5,WOLF:5,AVGO:4,QCOM:4,STM:4,
MKSI:4,COHR:3,TSEM:3""")

_put("원전·우라늄", """
CCJ:5,BWXT:5,OKLO:5,NXE:5,UEC:5,SMR:5,LEU:5,UUUU:5,DNN:5,UROY:5,NNE:5,ISOU:5,
URG:5,EU:5,CEG:4,TLN:4,ASPI:4,LTBR:4,GEV:3,SO:3,DUK:3,D:3,VST:3,PEG:3,FRMI:3,
NEE:2,ETR:2,XEL:2,EXC:2,AEE:2,DTE:2,FLR:2""")

_put("방산·군수", """
RTX:5,LMT:5,GD:5,NOC:5,LHX:5,HII:5,DRS:5,PLTR:4,BA:4,ESLT:4,CW:4,LDOS:4,CACI:4,
KTOS:4,AVAV:4,BAH:4,KRMN:4,SAIC:4,VVX:4,GE:3,HWM:3,TDG:3,HEI:3,RKLB:3,TDY:3,
WWD:3,BWXT:3,TXT:3,OSK:3,MRCY:3,PSN:3,RDW:3,VOYG:3,RCAT:3,ATI:2,CRS:2,VSAT:2,
KBR:2,OSIS:2,DCO:2,BBAI:2,HON:1,AXON:1""")

_put("사이버보안", """
PANW:5,CRWD:5,FTNT:5,ZS:5,OKTA:5,RBRK:5,GEN:5,CHKP:5,SAIL:5,S:5,QLYS:5,VRNS:5,
TENB:5,RPD:5,NET:4,FFIV:4,AKAM:4,NTCT:4,RDWR:4,OSPN:4,TLS:4,GOOGL:3,MSFT:3,
AMZN:3,AVGO:3,CSCO:3,IBM:3,DT:3,ESTC:3""")

_put("우주·위성", """
RKLB:5,ASTS:5,MDA:5,FLY:5,LUNR:5,VOYG:5,SATS:4,VSAT:4,GSAT:4,PL:4,KRMN:4,
IRDM:4,RDW:4,YSS:4,BKSY:4,TSAT:4,SATL:4,SPIR:4,SPCE:4,RTX:3,BA:3,LMT:3,NOC:3,
LHX:3,KTOS:3,MRCY:3,GILT:3,AMZN:2,APH:2,VZ:2,TMUS:2,GD:2,LDOS:2,CACI:2,HII:2,
DRS:2,SAIC:2,MMM:1,HEI:1,IR:1,CW:1""")

_put("양자컴퓨팅", """
IONQ:5,QBTS:5,RGTI:5,INFQ:5,QUBT:5,BTQ:5,LAES:5,ARQQ:5,NVDA:4,GOOGL:4,MSFT:4,
AMZN:4,INTC:4,IBM:4,HON:4,COHR:3,LITE:3,KEYS:3,GFS:3,MKSI:3,FORM:3,AEHR:3,
LASR:3,MRVL:2,TER:2,TSEM:2,FN:2,IPGP:2""")

_put("로봇·자동화", """
ISRG:5,TER:5,CGNX:5,SYM:5,PRCT:5,SERV:5,RR:5,ROK:4,AVAV:4,PATH:4,ATS:4,RCAT:4,
PDYN:4,NVDA:3,ETN:3,PH:3,SYK:3,EMR:3,HON:3,AME:3,DOV:3,ZBRA:3,NDSN:3,NVMI:3,
OMCL:3,AMZN:2,TSLA:2,DE:2,ROP:2,HUBB:2,GGG:2,KTOS:2""")

_put("데이터센터", """
VRT:5,EQIX:5,DLR:5,CRWV:5,NBIS:5,SMCI:5,IREN:5,APLD:5,CORZ:5,WYFI:5,ANET:4,
MRVL:4,AMT:4,ALAB:4,CRDO:4,IRM:4,SBAC:4,TLN:4,WULF:4,GDS:4,UNIT:4,VNET:4,
DELL:3,GEV:3,ETN:3,GLW:3,PWR:3,CEG:3,HPE:3,COHR:3,BE:3,FIX:3,CIEN:3,VST:3,
CCI:3,LUMN:3,EME:2,HUBB:2,J:2,MOD:2,WCC:1""")

_put("석유·가스", """
XOM:5,CVX:5,COP:5,PBR:5,CNQ:5,EOG:5,SU:5,IMO:5,OXY:5,FANG:5,CVE:5,LNG:5,DVN:5,
EQT:5,VG:5,EXE:5,PR:5,OVV:5,APA:5,AR:5,CHRD:5,SHEL:4,TTE:4,ENB:4,BP:4,EQNR:4,
MPC:4,VLO:4,PSX:4,WMB:4,EPD:4,SLB:4,ET:4,KMI:4,TRP:4,BKR:4,MPLX:4,OKE:4,
TRGP:4,FTI:4,HAL:4,WES:4,DINO:4,NOV:4,TPL:3""")

_put("전기차", """
TSLA:5,RIVN:5,LI:5,NIO:5,XPEV:5,VFS:5,LCID:5,PSNY:5,EVGO:5,CHPT:5,GM:4,F:4,
STLA:4,ALB:4,BWA:4,QS:4,VGNT:4,TM:3,CMI:3,PCAR:3,STM:3,ON:3,SQM:3,MP:3,LAC:3,
SLDP:3,FREY:3,PLL:3,NVDA:2,BHP:2,NEE:2,RIO:2,DUK:2,EXC:2,APTV:2,GOOGL:1,
MSFT:1,AMZN:1,WMT:1""")

_put("재생에너지", """
GEV:5,NEE:5,FSLR:5,NXT:5,ENLT:5,BEP:5,BEPC:5,ENPH:5,FLNC:5,CWEN:4,ORA:4,RNW:4,
RUN:4,SEDG:4,EOSE:4,SHLS:4,CSIQ:4,JKS:4,ARRY:4,BE:3,HASI:3,PLUG:3,AMRC:3,
XIFR:3,TSLA:2,CEG:2,VST:2,FCEL:2,GPRE:2,BLDP:2,GEVO:2,CLNE:2,UGI:1,QS:1,KYN:1,
ENVX:1,STEM:1""")

_put("바이오·제약", """
LLY:5,ABBV:5,MRK:5,NVS:5,AZN:5,AMGN:5,NVO:5,GILD:5,PFE:5,VRTX:5,BMY:5,SNY:5,
GSK:5,REGN:5,ARGX:5,BIIB:5,ALNY:5,INCY:5,MRNA:5,BNTX:5,NBIX:5,BMRN:5,EXEL:5,
IONS:5,CRSP:5,BEAM:5,NTLA:5,JNJ:4,TAK:4,RVMD:4,TEVA:4,INSM:4,UTHR:4,GMAB:4,
ASND:4,JAZZ:4,ARWR:4,MDGL:4,SMMT:4,AXSM:4,CYTK:4,KRYS:4,PCVX:4,RYTM:4,VKTX:4,
RARE:4,SRPT:4,ZTS:3,ROIV:3,VTRS:3,HALO:3""")

_put("암호화폐·블록체인", """
COIN:5,MSTR:5,CRCL:5,RIOT:5,GLXY:5,MARA:5,BLSH:5,BTDR:5,XXI:5,HIVE:5,BTGO:5,
GEMI:5,ABTC:5,XYZ:4,IREN:4,HUT:4,BMNR:4,WULF:4,CIFR:4,CORZ:4,FIGR:4,CLSK:4,
SBET:4,BITF:4,BTBT:4,CNCK:4,EXOD:4,CME:3,HOOD:3,PYPL:3,ETOR:3,ASST:3,BKKT:3,
TSLA:2,JPM:2,V:2,MA:2,GS:2,GME:2,RUM:2""")

_put("금·귀금속", """
NEM:5,AEM:5,WPM:5,AU:5,FNV:5,GFI:5,KGC:5,PAAS:5,RGLD:5,CDE:5,AGI:5,EQX:5,HMY:5,
HL:5,IAG:5,EGO:5,AG:5,BTG:5,TFPM:5,SSRM:5,OGC:5,OR:5,AYA:5,ARIS:5,ORLA:5,SA:5,
NG:5,FSM:5,EXK:5,AAUC:5,SVM:5,DRD:5,USAS:5,GROY:5,B:4,CGAU:4,PPTA:4,IAUX:4,
VZLA:4,ASM:4,MUX:4,CMCL:3""")

_put("물·수처리", """
XYL:5,AWK:5,VLTO:5,WTS:5,PNR:5,CNM:5,ZWS:5,FELE:5,MWA:5,BMI:5,AWR:5,CWT:5,
HTO:5,MSEX:5,YORW:5,CWCO:5,ARTNA:5,GWRS:5,ECL:4,SBS:4,WTRG:4,WMS:4,TTEK:4,
AOS:4,PRMB:4,ERII:4,CDZI:4,PCYO:4,IEX:3,FLS:3,ITRI:3,LNN:3,ROP:2,GGG:2""")


def members(theme: str, floor: int = 4) -> list[str]:
    """그 테마에서 affinity가 floor 이상인 티커."""
    return [t for t, s in STOCKTITAN[theme].items() if s >= floor]


if __name__ == "__main__":
    print(f"테마 {len(STOCKTITAN)}개")
    for name, table in STOCKTITAN.items():
        five = sum(1 for s in table.values() if s == 5)
        print(f"  {name:<14}{len(table):>3}개 (5점 {five}개)")
