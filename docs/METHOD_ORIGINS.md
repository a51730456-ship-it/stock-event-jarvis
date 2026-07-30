# 이 기법의 근원과 매도 시점 — 2026-07-30 조사

사용자 지시로 조사했다. 두 가지 물음이었다.

1. 자비스3·4가 쓰는 테마 레이더 방식은 **원래 어디서 나온 것인가. 논문인가?**
2. **언제 팔아야 하는가.** 지금 화면에는 그 답이 없다.

여기 적은 것은 조사 결과다. **우리 자료로 다시 잰 값이 아니다.**
화면 문구(`method_help.py`)에도 "남의 자료로 잰 값"이라고 못 박아 두었다.

---

## 1. 근원 — 한 편의 논문이 아니다

결론부터: **단일 논문에서 나온 기법이 아니다.** 학술 쪽 세 갈래와 실무 쪽 세 갈래가
따로 자라서 같은 결론에 닿았고, 자비스는 그 공통분모를 점수로 바꾼 것이다.

### 1-1. 학술 쪽

| 논문 | 무엇을 보였나 | 자비스의 어느 부분 |
|---|---|---|
| Jegadeesh & Titman (1993), *JF* | 개별 종목 모멘텀의 원형 — 오른 것을 사고 내린 것을 파는 전략이 통했다 | 전체 뼈대 |
| **Moskowitz & Grinblatt (1999), *JF*** | **산업(분야) 모멘텀이 개별 종목 모멘텀의 상당 부분을 설명한다.** 개별 모멘텀은 산업을 통제하면 크게 약해진다. 산업 모멘텀의 이익은 **파는 쪽보다 사는 쪽**에서 나오고, **가장 크고 유동성 높은 종목**에서 나온다 (NYSE·AMEX·Nasdaq, 1963-07 ~ 1995-07, 2자리 SIC) | **테마를 먼저 세우고 → 그 안에서 대장주를 고르는 구조 자체.** 유동성 배점(15점)의 근거이기도 하다 |
| **George & Hwang (2004), *JF*** | **현재가 ÷ 52주 최고가** 비율이 과거 수익률(개별·산업 둘 다)보다 예측력이 좋았다. 그리고 이 신호로 고른 것은 **장기적으로 되돌아가지 않았다** (상위 30% 매수, 6~12개월 보유) | **'52주 신고가 위치'** 항목 (미국 25점 · 한국 15점) |
| **Moskowitz, Ooi & Pedersen (2012), *JFE*** | 시계열 모멘텀 — 58개 선물의 과거 12개월 수익이 미래를 예측하고, **추세는 약 1년 지속 후 부분 반전**한다 | 추세 항목, 그리고 시장 게이트(이동평균 위/아래) |

핵심은 **Moskowitz & Grinblatt (1999)**이다. "왜 종목이 아니라 테마부터 보는가"에
대한 답이 그 논문에 그대로 있다. 자비스의 구조가 우연히 맞아떨어진 게 아니라
이 결과와 같은 모양이다.

### 1-2. 실무 쪽

| 사람 | 언제 | 무엇 |
|---|---|---|
| Stan Weinstein | 1988 | **Stage Analysis** — 바닥(1)·상승(2)·천장(3)·하락(4) 네 단계. **30주(≈150일) 이동평균**이 기준선. 2단계에서만 산다 |
| William O'Neil | 1960년대~ | **CAN SLIM** — 바닥 다지기 후 신고가 돌파 매수. 상대강도 개념을 대중화 |
| Mark Minervini | 2010년대 | **Trend Template / SEPA** — Weinstein의 2단계를 8개 조건으로 못 박은 점검표 |

Minervini의 Trend Template은 Weinstein Stage 2의 엄격한 정량화판이다. 즉 실무 쪽도
한 줄기다.

### 1-3. 그래서 자비스는

- 시장 게이트(이동평균) ← Moskowitz·Ooi·Pedersen + Weinstein
- 테마 먼저 ← **Moskowitz & Grinblatt**
- 52주 신고가 위치 ← **George & Hwang**
- 상대강도 ← Jegadeesh·Titman + O'Neil
- 돌파 확인 / 눌림목 대기 ← O'Neil(돌파) + Weinstein·Minervini(2단계 눌림)

---

## 2. 매도 시점 — 지금 앱의 상태

### 2-1. 현재 있는 것

`jarvis3_data._entry_plan` / `jarvis4_data`가 **진입 시점에 한 번** 계산한다.

- `invalidation` (무효화 가격) — 현재가 − max(ATR×2, 현재가×3%) *(한국 4%)*
- `target` (2R 목표) — 기준가 + 2 × (기준가 − 무효화가격)

`jarvis3_store.close_trade` / `jarvis4_store.close_trade`는 **사용자가 손으로 넣은**
매도일·매도가를 받아 손익만 계산한다.

### 2-2. 없는 것

- 보유 중 갱신되는 매도 신호가 **없다**
- 추격 손절(트레일링 스톱)이 **없다**
- 시간 기준 청산이 **없다**
- 추세 이탈(이동평균 하향 돌파) 경보가 **없다**

즉 **진입만 있고 퇴장이 없다.** 사용자가 이 점을 정확히 짚었다.

### 2-3. 연구·실무가 말하는 매도 규칙

| 방식 | 출처 | 숫자 | 근거의 세기 |
|---|---|---|---|
| 고정 손절 | **Han, Zhou & Zhu**, *Taming Momentum Crashes* | 월초 가격 대비 **−10%**면 청산. 1926-01~2013-12 미국 주식. 최대 월손실 **−49.79% → −11.36%**(동일가중), **−64.97% → −23.28%**(시총가중). 샤프비율 2배 이상. 평균 월수익 1.01% → 1.73% | **강함** — 88년치, 최악 4개월 −49.79/−39.43/−35.24/−34.46% → −9.62/+2.83/−10.76/−17.43% |
| 고정 손절 | O'Neil | 매수가 대비 **−7~8%** | 실무 경험칙 |
| 부분 익절 | O'Neil | **+20~25%**에서 일부 청산. 단 돌파 후 1~3주 안에 +20% 이상이면 **8주 보유** | 실무 경험칙 |
| 추세 이탈 | Weinstein | 기준 이동평균 하향 돌파(3→4단계) | 실무 경험칙 |
| 시간 청산 | Moskowitz·Ooi·Pedersen | 추세는 **약 12개월** 후 부분 반전 | 학술 |

**가장 재볼 값어치가 있는 것은 Han·Zhou·Zhu의 −10% 규칙이다.** 이유:

1. 학술 논문이고 88년치 표본이다
2. 규칙이 단순해서 우리 자료로 그대로 재현할 수 있다
3. 자비스가 지금 잘하는 것(= 크게 깨지는 것 막기)과 목적이 같다.
   2026-07-29 검증에서 50일선은 "수익 예측이 아니라 손실 방어"였다.
   손절 규칙도 같은 축이다

### 2-4. 다음에 할 일 (아직 안 함)

1. 코스피·S&P500 21년치로 위 다섯 규칙을 각각 재본다
2. 우리 시장에서 **듣는 것만** 화면에 넣는다
3. `jarvis3_data`/`jarvis4_data`에 보유 중 갱신되는 매도 신호를 넣을지 결정한다
   — **넣기 전에 숫자부터.** 2026-07-29의 교훈이다

> 종목 단위로 과거검증하면 '오늘 살아남은 종목만 모으는' 편향이 낀다.
> 지수로 재거나, 상장폐지 포함 명부를 구해야 한다. (2026-07-29 검증에서 확인)

---

## 출처

- [Moskowitz & Grinblatt (1999), "Do Industries Explain Momentum?", *Journal of Finance* 54(4), 1249-1290](https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00146) · [PDF](http://www-stat.wharton.upenn.edu/~steele/Courses/956/Resource/Momentum/MoskowitzGrinblatt99.pdf)
- [George & Hwang (2004), "The 52-Week High and Momentum Investing", *Journal of Finance* 59, 2145-2176](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2004.00695.x)
- [Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum", *JFE* 104(2), 228-250](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum)
- [Han, Zhou & Zhu, "Taming Momentum Crashes: A Simple Stop-Loss Strategy" (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2407199) · [PDF](https://www.cicfconf.org/sites/default/files/paper_811.pdf)
- [Stan Weinstein Stage Analysis 정리 (TraderLion)](https://traderlion.com/trading-strategies/stage-analysis/)
- [CAN SLIM (Wikipedia)](https://en.wikipedia.org/wiki/CAN_SLIM)
- [O'Neil 8주 보유 규칙 (TraderLion)](https://traderlion.com/trading-strategies/the-8-week-hold-rule/)
