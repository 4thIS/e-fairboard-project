import { describe, it, expect } from 'vitest'
import { advanceOf, isRenderable, measure, clip, utf8Bytes } from './text'

describe('advanceOf — ASCII 반각 8px, 한글 전각 16px', () => {
  it('ASCII 는 8px', () => expect(advanceOf('A')).toBe(8))
  it('숫자도 8px', () => expect(advanceOf('7')).toBe(8))
  it('공백도 8px', () => expect(advanceOf(' ')).toBe(8))
  it('한글은 16px', () => expect(advanceOf('가')).toBe(16))
})

describe('isRenderable — 노드 폰트에 있는 글자만', () => {
  it('ASCII 통과', () => expect(isRenderable('A')).toBe(true))
  it('한글 통과', () => expect(isRenderable('힣')).toBe(true))
  it('한자는 없다', () => expect(isRenderable('漢')).toBe(false))
  it('이모지도 없다', () => expect(isRenderable('🎉')).toBe(false))
})

describe('measure', () => {
  it('한글 3자 x1 = 48px', () => expect(measure('경진대', 1)).toBe(48))
  it('scale 2 면 2배', () => expect(measure('경진대', 2)).toBe(96))
  it('한글+ASCII 혼합', () => {
    // '가' 16 + 'A' 8 + 'B' 8 = 32
    expect(measure('가AB', 1)).toBe(32)
  })
  it('없는 글자는 폭을 안 준다 — 노드도 자리를 안 준다', () => {
    expect(measure('가漢나', 1)).toBe(32)
  })
})

describe('clip — 넘치는 글자는 통째로 버린다 (반쪽 글자를 만들지 않는다)', () => {
  it('다 들어가면 그대로', () => {
    expect(clip('경진대회', 288, 1)).toEqual({ text: '경진대회', clipped: false })
  })
  it('딱 맞으면 안 자른다', () => {
    // 한글 4자 x 16 = 64
    expect(clip('경진대회', 64, 1)).toEqual({ text: '경진대회', clipped: false })
  })
  it('1px 모자라면 마지막 글자를 통째로 버린다', () => {
    expect(clip('경진대회', 63, 1)).toEqual({ text: '경진대', clipped: true })
  })
  it('scale 2 에서는 절반만 들어간다', () => {
    // 32px/자 → 64px 에는 2자
    expect(clip('경진대회', 64, 2)).toEqual({ text: '경진', clipped: true })
  })
  it('실제 사례 — 제목 288px 에 "임베디드 SW 경진대회"', () => {
    // 한글 8자 x16 = 128, 공백 2 + SW 2 = ASCII 4자 x8 = 32 → 총 160 <= 288
    expect(clip('임베디드 SW 경진대회', 288, 1).clipped).toBe(false)
  })
  it('실제 사례 — 32px 이면 같은 제목이 잘린다 (216px 가용)', () => {
    // 32px/한글자, 16px/ASCII → 8*32 + 4*16 = 320 > 216
    expect(clip('임베디드 SW 경진대회', 216, 2).clipped).toBe(true)
  })
})

describe('utf8Bytes — 서버 max_bytes 검증과 같은 기준', () => {
  it('한글은 3바이트', () => expect(utf8Bytes('가')).toBe(3))
  it('ASCII 는 1바이트', () => expect(utf8Bytes('A')).toBe(1))
  it('혼합', () => expect(utf8Bytes('가A')).toBe(4))
})
