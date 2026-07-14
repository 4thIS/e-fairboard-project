import { AxiosError } from 'axios'
import { describe, expect, it } from 'vitest'
import { errorMessage } from './client'

/** 서버가 꺼진 것과 비밀번호가 틀린 것을 같은 문구로 말하면,
 *  사용자는 멀쩡한 비밀번호를 계속 다시 친다. 그 구분을 여기서 못 박는다. */
const withStatus = (status: number) =>
  new AxiosError('x', undefined, undefined, undefined, {
    status, data: {}, statusText: '', headers: {}, config: {} as never,
  })

describe('errorMessage', () => {
  it('401 은 호출자가 준 문구를 쓴다', () => {
    expect(errorMessage(withStatus(401), '비밀번호가 올바르지 않습니다'))
      .toBe('✕ 비밀번호가 올바르지 않습니다')
  })

  it('응답이 아예 없으면(서버 다운) 연결 문제라고 말한다', () => {
    expect(errorMessage(new AxiosError('Network Error'), '비밀번호가 올바르지 않습니다'))
      .toContain('서버에 연결할 수 없습니다')
  })

  it('422 는 입력 검증 실패로 구분한다', () => {
    expect(errorMessage(withStatus(422), '아무거나')).toContain('서버 검증')
  })

  it('그 밖의 상태코드는 서버 오류로 코드를 밝힌다', () => {
    expect(errorMessage(withStatus(500), '아무거나')).toBe('✕ 서버 오류 (500)')
  })
})
