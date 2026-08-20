import { describe, it, expect } from 'vitest'
import { advancePx, isRenderable, measure, clip, utf8Bytes } from './text'

describe('advancePx — ASCII 반각(px/2), 한글 전각(px)', () => {
  it('ASCII 는 절반', () => expect(advancePx('A', 72)).toBe(36))
  it('숫자도 절반', () => expect(advancePx('7', 56)).toBe(28))
  it('공백도 절반', () => expect(advancePx(' ', 40)).toBe(20))
  it('한글은 전각', () => expect(advancePx('가', 72)).toBe(72))
  it('px 16 이면 8/16 (옛 기준)', () => {
    expect(advancePx('A', 16)).toBe(8)
    expect(advancePx('가', 16)).toBe(16)
  })
})

describe('isRenderable — 노드 폰트 범위(ASCII + 완성형 한글)', () => {
  it('ASCII 통과', () => expect(isRenderable('A')).toBe(true))
  it('한글 통과', () => expect(isRenderable('힣')).toBe(true))
  it('한자는 없다', () => expect(isRenderable('漢')).toBe(false))
  it('이모지도 없다', () => expect(isRenderable('🎉')).toBe(false))
  it('한글 범위 경계 — U+D7A4(힣 바로 다음)는 없다', () => {
    expect(isRenderable('힤')).toBe(false)
  })
})

describe('measure', () => {
  it('한글 3자 x16 = 48px', () => expect(measure('경진대', 16)).toBe(48))
  it('한글 3자 x72 = 216px', () => expect(measure('경진대', 72)).toBe(216))
  it('한글+ASCII 혼합 (72): 가72 + A36 + B36 = 144', () => {
    expect(measure('가AB', 72)).toBe(144)
  })
  it('없는 글자는 폭을 안 준다 — 노드도 자리를 안 준다', () => {
    expect(measure('가漢나', 72)).toBe(144)
  })
})

describe('clip — 넘치는 글자는 통째로 버린다 (반쪽 글자를 만들지 않는다)', () => {
  it('다 들어가면 그대로', () => {
    expect(clip('경진대회', 288, 16)).toEqual({ text: '경진대회', clipped: false })
  })
  it('딱 맞으면 안 자른다 (한글 4자 x16 = 64)', () => {
    expect(clip('경진대회', 64, 16)).toEqual({ text: '경진대회', clipped: false })
  })
  it('1px 모자라면 마지막 글자를 통째로 버린다', () => {
    expect(clip('경진대회', 63, 16)).toEqual({ text: '경진대', clipped: true })
  })
  it('72px 이면 4자에 288px 필요 — 216px 엔 3자만', () => {
    expect(clip('경진대회', 216, 72)).toEqual({ text: '경진대', clipped: true })
  })
  it('실제 사례 — 제목 "임베디드 SW 경진대회" 가 72px 로 부스가용 1256px 에 들어간다', () => {
    // 한글 8자 x72 = 576, 공백2 x36 + SW 2 x36 = ASCII 4자 x36 = 144 → 총 720 <= 1256
    expect(clip('임베디드 SW 경진대회', 1256, 72).clipped).toBe(false)
  })
  it('같은 제목이 좁은 폭(600px)에선 잘린다', () => {
    expect(clip('임베디드 SW 경진대회', 600, 72).clipped).toBe(true)
  })
  it('안 들어가는 글자를 만나면 그 자리에서 멈춘다 — 뒤 좁은 글자도 안 훑는다', () => {
    // '가'(16)→pen16. '가'(16)는 32>24 로 못 들어가 즉시 멈춘다. 뒤의 'A'(8)는 보지 않는다.
    expect(clip('가가A', 24, 16)).toEqual({ text: '가', clipped: true })
  })
  it('없는 글자는 clip 에서도 폭을 안 먹고 출력에도 안 남는다', () => {
    expect(clip('가漢나', 32, 16)).toEqual({ text: '가나', clipped: false })
  })
})

describe('utf8Bytes — 서버 max_bytes 검증과 같은 기준', () => {
  it('한글은 3바이트', () => expect(utf8Bytes('가')).toBe(3))
  it('ASCII 는 1바이트', () => expect(utf8Bytes('A')).toBe(1))
  it('혼합', () => expect(utf8Bytes('가A')).toBe(4))
})

describe('세로 캔버스 본문 56px (가용 936px)', () => {
  it('한글 16자는 들어가고 17자째는 통째로 버린다 (16*56=896, 17*56=952)', () => {
    expect(clip('일이삼사오육칠팔구십일이삼사오육', 936, 56).clipped).toBe(false)
    expect(clip('일이삼사오육칠팔구십일이삼사오육칠', 936, 56).clipped).toBe(true)
  })
})
