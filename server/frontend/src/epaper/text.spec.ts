import { describe, it, expect } from 'vitest'
import { advancePx, isRenderable, measure, clip, utf8Bytes } from './text'

// font_advance.json 실제 값(나눔스퀘어 Bold): 가=[36,51,66] A=[27,38,48] W=[39,55,70] 공백=[15,20,26]
describe('advancePx — 비례폭 테이블 (40/56/72)', () => {
  it('한글 가 72=66', () => expect(advancePx('가', 72)).toBe(66))
  it('한글 가 40=36, 56=51', () => {
    expect(advancePx('가', 40)).toBe(36)
    expect(advancePx('가', 56)).toBe(51)
  })
  it('ASCII A 72=48 (반각 아님)', () => expect(advancePx('A', 72)).toBe(48))
  it('W 는 거의 전각 (72=70)', () => expect(advancePx('W', 72)).toBe(70))
  it('공백 72=26', () => expect(advancePx(' ', 72)).toBe(26))
  it('테이블에 없는 크기는 전각 폴백', () => expect(advancePx('가', 64)).toBe(64))
})

describe('isRenderable — ASCII + baked 한글(2,000자 테이블)', () => {
  it('ASCII 통과', () => expect(isRenderable('A')).toBe(true))
  it('흔한 한글 통과', () => expect(isRenderable('가')).toBe(true))
  it('한자는 없다', () => expect(isRenderable('漢')).toBe(false))
  it('이모지도 없다', () => expect(isRenderable('🎉')).toBe(false))
})

describe('measure — 비례폭 합', () => {
  it('ASCII A 3자 x72 = 144', () => expect(measure('AAA', 72)).toBe(144))
  it('가(66) + A(48) = 114', () => expect(measure('가A', 72)).toBe(114))
  it('없는 글자는 폭 0 (한자 스킵)', () => expect(measure('가漢A', 72)).toBe(114))
})

describe('clip — 넘치는 글자는 통째로 버린다', () => {
  it('가가(132) 딱 맞으면 안 자른다', () => {
    expect(clip('가가', 132, 72)).toEqual({ text: '가가', clipped: false })
  })
  it('가가가 는 132px 에 2자만 (3자째 198>132)', () => {
    expect(clip('가가가', 132, 72)).toEqual({ text: '가가', clipped: true })
  })
  it('가가가 198px 에 다 들어간다', () => {
    expect(clip('가가가', 198, 72).clipped).toBe(false)
  })
  it('AAAA 100px 엔 2자 (48*2=96, 3자째 144>100)', () => {
    expect(clip('AAAA', 100, 72)).toEqual({ text: 'AA', clipped: true })
  })
  it('없는 글자는 clip 에서도 폭을 안 먹고 출력에도 안 남는다', () => {
    // 가(66) + 漢(0, 스킵) + A(48) = 114
    expect(clip('가漢A', 114, 72)).toEqual({ text: '가A', clipped: false })
  })
})

describe('utf8Bytes — 서버 max_bytes 검증과 같은 기준', () => {
  it('한글은 3바이트', () => expect(utf8Bytes('가')).toBe(3))
  it('ASCII 는 1바이트', () => expect(utf8Bytes('A')).toBe(1))
  it('혼합', () => expect(utf8Bytes('가A')).toBe(4))
})
