import { describe, it, expect } from 'vitest'
import { advanceOf, isRenderable, measure, clip, utf8Bytes, scaleFor } from './text'

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
  it('한글 범위 경계 — U+D7A4(힣 바로 다음)는 없다', () => {
    expect(isRenderable('힤')).toBe(false)
  })
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
  it('안 들어가는 글자를 만나면 그 자리에서 멈춘다 — 뒤에 더 좁은 글자가 있어도 훑지 않는다', () => {
    // '가'(16) 들어감→pen=16. '가'(16)는 16+16=32>24 로 못 들어가 즉시 멈춘다.
    // 이어지는 'A'(8)는 16+8=24<=24 로 들어갈 수 있었겠지만, break 이므로 절대 보지 않는다.
    expect(clip('가가A', 24, 1)).toEqual({ text: '가', clipped: true })
  })
  it('없는 글자는 clip 에서도 폭을 안 먹고 출력에도 안 남는다', () => {
    // '가'(16) + '漢'(폭 0, 자리도 안 줌) + '나'(16) = 32, 정확히 32 에 맞는다
    expect(clip('가漢나', 32, 1)).toEqual({ text: '가나', clipped: false })
  })
})

describe('utf8Bytes — 서버 max_bytes 검증과 같은 기준', () => {
  it('한글은 3바이트', () => expect(utf8Bytes('가')).toBe(3))
  it('ASCII 는 1바이트', () => expect(utf8Bytes('A')).toBe(1))
  it('혼합', () => expect(utf8Bytes('가A')).toBe(4))
})

describe('scaleFor — 노드 scale_for 과 동일 (node_core/layout.cpp)', () => {
  it('16 -> 1', () => expect(scaleFor(16)).toBe(1))
  it('32 -> 2', () => expect(scaleFor(32)).toBe(2))
  it('16 미만은 내림하면 0 이 되지만 최소 x1 로 막는다 — 글자가 사라지면 안 된다', () => {
    expect(scaleFor(12)).toBe(1)
    expect(scaleFor(0)).toBe(1)
  })
  // 올림이면 24 -> 2 (=32px) 가 되어 글자가 잘린다. 펌웨어에서 실제로 터졌던 버그다:
  // "임베디드 SW 경진대회" 의 뒤가 날아갔다 (node_core/layout.h, test_layout 이 같은 케이스를 못 박는다).
  // 16/32 만 쓰는 지금은 안 터지지만, 반올림 방향은 이 파일이 지켜야 할 계약이다.
  it('24 -> 1 — 1.5 를 올림하지 않는다 (올리면 32px 로 그려서 잘린다)', () => {
    expect(scaleFor(24)).toBe(1)
    expect(scaleFor(20)).toBe(1)
  })
})
