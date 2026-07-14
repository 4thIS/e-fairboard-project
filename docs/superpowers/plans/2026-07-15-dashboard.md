# 대시보드 (다크 관제센터) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스펙 [docs/web/2026-07-14-dashboard-design.md](../../web/2026-07-14-dashboard-design.md)의 로그인 + 대시보드(노드 카드·편집 다이얼로그·배포 진행)를 구현한다.

**Architecture:** Vue 3 + Vite + TS + Pinia SPA(UI 프레임워크 없음, 다크 토큰 CSS). 검증된 자산(`epaper/text.ts`+테스트, API 클라이언트, auth 스토어, `EpaperPreview.vue`, Neo둥근모 폰트)은 git 이력 `d02d3ba`에서 복원한다. 백엔드는 두 곳만 확장: `DeployTarget` 단계 필드 3개, `GET /api/nodes` 목록에 `display_state` 포함.

**Tech Stack:** Vue 3.5 / Vite 8 / TypeScript 6 / Pinia 3 / axios / qrcode / vitest — FastAPI 백엔드는 기존 그대로.

## Global Constraints

- 브랜치 `wj`에서만 작업. main 직접 push 금지. `gateway/`·`node/` 수정 금지 (CLAUDE.md).
- `server/backend/app/protocol/`·`app/simulator/`는 건드리지 않는다 (스펙 §6.3).
- UI 프레임워크·CSS 라이브러리 추가 금지. 새 npm 의존성 추가 금지 (기존 restore 목록만).
- UI 문구는 한국어. 상태는 색+형태+텍스트 병행: `● ONLINE` `○ OFFLINE` `◈ 배포 중` `✕ 실패` (스펙 §4).
- 미리보기 렌더 규칙 파일(`src/epaper/text.ts`)은 복원만 하고 수정하지 않는다.
- 폴링 주기: nodes 5초, 진행 중 배포 1초 (스펙 §5).
- 커밋 메시지는 기존 관례(`feat(frontend): …` 한국어) + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 트레일러.
- 백엔드 테스트: `cd server/backend; python -m pytest -q` / 프론트: `cd server/frontend; npm test`.
- 알려진 한계 (스펙과의 의도적 차이): 진행 오버레이의 **실시간 재시도 횟수는 표시하지 않는다**.
  링크 계층(`link.py`)이 재시도를 내부에서 소화해 관측 불가 — 노출하려면 프로토콜 계층 변경이
  필요해 스펙 §6.3 제약과 충돌한다. 실패 시 `error` 문자열(`… after 4 attempts`)로 확인된다.

---

### Task 1: 백엔드 — DeployTarget 단계 필드 + 노드 목록 display_state

**Files:**
- Modify: `server/backend/app/models.py:34-39` (DeployTarget)
- Modify: `server/backend/app/services/deploy_service.py:51-58` (run_deployment)
- Modify: `server/backend/app/routers/nodes.py:22-25` (list_nodes)
- Test: `server/backend/tests/test_deployments_api.py`, `server/backend/tests/test_nodes_api.py`

**Interfaces:**
- Consumes: 기존 `build_packet_plan(post, refresh_mode) -> list[tuple[MsgType, bytes]]`, `MsgType.name` ("SET_TEMPLATE"|"SET_FIELD"|"SET_QR"|"COMMIT")
- Produces: `GET /api/deployments/{id}` targets에 `step_name: str, step_index: int, step_total: int` (1-base, 기본 0/""), `GET /api/nodes` 각 항목에 `display_state: {template_id, fields, qr_url} | null`

- [ ] **Step 1: 실패하는 테스트 2개 작성**

`server/backend/tests/test_deployments_api.py` 끝에 추가:

```python
def test_deploy_reports_step_progress(client, auth_headers):
    pid = make_post(client, auth_headers)
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": [1], "refresh_mode": 0},
                      headers=auth_headers)
    dep = wait_deployment(client, auth_headers, res.json()["id"])
    t = dep["targets"][0]
    # VALID_POST = 필드 2 + QR → SET_TEMPLATE + SET_FIELD×2 + SET_QR + COMMIT = 5
    assert t["step_total"] == 5
    assert t["step_index"] == 5          # 마지막 단계까지 진행
    assert t["step_name"] == "COMMIT"
```

`server/backend/tests/test_nodes_api.py` 끝에 추가:

```python
def test_list_nodes_includes_display_state(client, auth_headers):
    nodes = client.get("/api/nodes", headers=auth_headers).json()
    assert all("display_state" in n for n in nodes)
```

- [ ] **Step 2: 실패 확인**

Run: `cd server/backend; python -m pytest tests/test_deployments_api.py::test_deploy_reports_step_progress tests/test_nodes_api.py::test_list_nodes_includes_display_state -v`
Expected: 2 FAILED (`KeyError: 'step_total'` / `AssertionError` — display_state 없음)

- [ ] **Step 3: 구현**

`server/backend/app/models.py`의 `DeployTarget`에 필드 추가:

```python
class DeployTarget(BaseModel):
    node_id: int
    status: Literal["pending", "sending", "success", "failed"] = "pending"
    attempts: int = 0
    error: str = ""
    acked_at: datetime | None = None
    step_name: str = ""    # 현재/마지막 단계 — MsgType.name ("SET_TEMPLATE"…)
    step_index: int = 0    # 1-base. 0 = 아직 시작 안 함
    step_total: int = 0
```

`server/backend/app/services/deploy_service.py`의 `run_deployment` 내부 루프 교체 (기존 51~58행):

```python
    for target in dep.targets:  # 순차 유니캐스트 (스펙 §5.5)
        target.status = "sending"
        store.save()
        try:
            for i, (msg_type, payload) in enumerate(plan, start=1):
                target.step_name = msg_type.name
                target.step_index = i
                target.step_total = len(plan)
                target.attempts += 1
                store.save()  # 1초 폴링이 단계 진행을 보게 한다 (스펙 §6.3)
                await rig.link.request(target.node_id, msg_type, payload,
                                       expect=MsgType.ACK)
```

`server/backend/app/routers/nodes.py`의 `list_nodes` 교체 (`node_detail`과 같은 규칙):

```python
@router.get("")
def list_nodes(store: Store = Depends(get_store),
               rig=Depends(get_rig)) -> list[dict]:
    out = []
    for n in sorted(store.state.nodes.values(), key=lambda n: n.id):
        data = n.model_dump(exclude={"history"}, mode="json")
        data["display_state"] = (
            rig.nodes[n.id].display_state
            if rig is not None and n.id in rig.nodes else None)
        out.append(data)
    return out
```

- [ ] **Step 4: 새 테스트 통과 확인**

Run: `cd server/backend; python -m pytest tests/test_deployments_api.py tests/test_nodes_api.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 전체 백엔드 테스트 — 회귀 없음 확인**

Run: `cd server/backend; python -m pytest -q`
Expected: 전부 PASS (기존 테스트 포함)

- [ ] **Step 6: 커밋**

```bash
git add server/backend
git commit -m "feat(backend): DeployTarget 단계 필드 + 노드 목록에 display_state

대시보드 카드가 배포 단계(SET_FIELD 2/3…)를 실시간 표시하고, 목록
폴링만으로 미리보기를 그릴 수 있게 한다 (스펙 §6.3, §6.1).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 프론트 스캐폴드 — git 이력 복원 + 의존성 정리

**Files:**
- Restore(= `git checkout d02d3ba -- <path>`): `server/frontend/index.html`, `server/frontend/.gitignore`, `server/frontend/package.json`, `server/frontend/tsconfig.json`, `server/frontend/tsconfig.app.json`, `server/frontend/tsconfig.node.json`, `server/frontend/vite.config.ts`, `server/frontend/public/favicon.svg`, `server/frontend/public/fonts/NeoDunggeunmo.woff2`, `server/frontend/public/fonts/SOURCES.txt`, `server/frontend/src/epaper/text.ts`, `server/frontend/src/epaper/text.spec.ts`, `server/frontend/src/epaper/types.ts`, `server/frontend/src/api/client.ts`, `server/frontend/src/api/index.ts`, `server/frontend/src/stores/auth.ts`, `server/frontend/src/components/EpaperPreview.vue`, `server/frontend/src/router/index.ts`
- Modify: `server/frontend/package.json` (element-plus·chart.js 제거), `server/frontend/index.html` (title), `server/frontend/src/api/index.ts` (step 필드), `server/frontend/src/router/index.ts` (라우트 2개로 축소)

**Interfaces:**
- Consumes: git 이력 `d02d3ba`의 파일들 (그대로 복원)
- Produces: 이후 태스크가 쓰는 모듈 — `epaper/text.ts`의 `scaleFor(fontPx): number`, `measure(text, scale): number`, `clip(text, maxW, scale): {text, clipped}`, `utf8Bytes(text): number`, `advanceOf(ch): number`, `GLYPH_CELL=16` · `epaper/types.ts`의 `TemplateDef {id, name, fields: FieldDef[], qr: QrDef}`, `FieldDef {id, name, x, y, font_size, max_bytes, avail_w}`, `CANVAS_W=296, CANVAS_H=128` · `api`의 `api.*` 함수들과 `Post, NodeInfo, DeployTarget, Deployment` 타입 · `stores/auth.ts`의 `useAuth()` (`token`, `login(pw)`, `logout()`) · `components/EpaperPreview.vue` (props: `template: TemplateDef|null, fields: Record<string,string>, qrUrl?: string, scale?: number`)

- [ ] **Step 1: 이력에서 파일 복원**

```bash
git checkout d02d3ba -- server/frontend/index.html server/frontend/.gitignore server/frontend/package.json server/frontend/tsconfig.json server/frontend/tsconfig.app.json server/frontend/tsconfig.node.json server/frontend/vite.config.ts server/frontend/public/favicon.svg server/frontend/public/fonts/NeoDunggeunmo.woff2 server/frontend/public/fonts/SOURCES.txt server/frontend/src/epaper/text.ts server/frontend/src/epaper/text.spec.ts server/frontend/src/epaper/types.ts server/frontend/src/api/client.ts server/frontend/src/api/index.ts server/frontend/src/stores/auth.ts server/frontend/src/components/EpaperPreview.vue server/frontend/src/router/index.ts
```

주의: Pretendard woff2, element-overrides.css, 기존 views/, 다른 stores/는 복원하지 **않는다** (재작성 대상).

- [ ] **Step 2: package.json 정리**

`server/frontend/package.json`의 dependencies에서 `"element-plus"`와 `"chart.js"` 두 줄을 삭제한다. 나머지(axios·pinia·qrcode·vue·vue-router)는 유지. devDependencies는 그대로.

- [ ] **Step 3: index.html title 교체**

`<title>frontend</title>` → `<title>E-FairBoard</title>`, `<html lang="en">` → `<html lang="ko">`.

- [ ] **Step 4: api/index.ts에 step 필드 추가**

`DeployTarget` 인터페이스를 다음으로 교체 (Task 1의 백엔드와 1:1):

```ts
export interface DeployTarget {
  node_id: number; status: 'pending' | 'sending' | 'success' | 'failed'
  attempts: number; error: string; acked_at: string | null
  step_name: string; step_index: number; step_total: number
}
```

- [ ] **Step 5: 라우터를 2개 라우트로 축소**

`server/frontend/src/router/index.ts`의 `routes` 배열을 교체 (가드는 그대로 둔다):

```ts
  routes: [
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/', component: () => import('../views/DashboardView.vue') },
  ],
```

- [ ] **Step 6: 설치 + 복원된 테스트 통과 확인**

Run: `cd server/frontend; npm install; npm test`
Expected: `text.spec.ts` 전부 PASS (`npm install`이 element-plus 제거를 반영해 lock 재생성)

- [ ] **Step 7: 커밋**

```bash
git add server/frontend
git commit -m "feat(frontend): 스캐폴드 복원 — 검증된 자산은 이력에서 (d02d3ba)

epaper 렌더 규칙(+테스트)·API 클라이언트·auth 스토어·EpaperPreview·
Neo둥근모를 복원하고 element-plus/chart.js 를 걷어낸다 (스펙 §2 스택).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 다크 토큰 + 앱 엔트리 + 로그인

**Files:**
- Create: `server/frontend/src/styles/tokens.css`, `server/frontend/src/styles/base.css`, `server/frontend/src/main.ts`, `server/frontend/src/App.vue`, `server/frontend/src/views/LoginView.vue`, `server/frontend/src/views/DashboardView.vue` (임시 골격 — Task 5에서 완성)

**Interfaces:**
- Consumes: `useAuth()` (Task 2), router (Task 2)
- Produces: CSS 변수 `--bg --panel --border --input-bg --text --muted --ok --err --busy --action --ink --paper --mono`, 클래스 `.pix`(픽셀 폰트) `.btn .btn-primary .input` — 이후 모든 컴포넌트가 사용

- [ ] **Step 1: tokens.css 작성**

`server/frontend/src/styles/tokens.css`:

```css
/* 다크 관제센터 팔레트 (스펙 §4) */
:root {
  --bg:        #0E1116;   /* 페이지 배경 */
  --panel:     #161B22;   /* 카드·다이얼로그 */
  --border:    #2D333B;   /* 패널 테두리·구분선 */
  --input-bg:  #0E1116;
  --text:      #E6EDF3;
  --muted:     #8B949E;
  --ok:        #3FB950;   /* 온라인·성공 */
  --err:       #F85149;   /* 오프라인·실패·경고 */
  --busy:      #D29922;   /* 배포 중 */
  --action:    #238636;   /* 주요 버튼 */

  /* e-Paper 미리보기 내부 — EpaperPreview.vue 가 참조 (복원 코드와 이름 계약) */
  --ink:       #1A1A1A;
  --paper:     #FFFFFF;

  --mono: ui-monospace, Consolas, 'D2Coding', monospace;
}
```

- [ ] **Step 2: base.css 작성**

`server/frontend/src/styles/base.css`:

```css
@font-face {
  font-family: 'NeoDunggeunmo';
  src: url('/fonts/NeoDunggeunmo.woff2') format('woff2');
  font-display: block;   /* 미리보기 글자가 폴백 폰트로 먼저 그려지면 안 된다 */
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--mono);
  font-size: 14px;
}

/* 픽셀 폰트 — 미리보기 내부 전용. 보간 금지 (스펙: 노드와 픽셀 동일) */
.pix {
  font-family: 'NeoDunggeunmo', monospace;
  -webkit-font-smoothing: none;
  font-smooth: never;
}

.btn {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font: inherit;
  font-size: 13px;
  padding: 6px 14px;
  cursor: pointer;
}
.btn:disabled { color: var(--muted); cursor: not-allowed; }
.btn-primary { background: var(--action); border-color: var(--action); color: #fff; font-weight: 600; }
.btn-primary:disabled { background: var(--panel); border-color: var(--border); }

.input, select.input {
  background: var(--input-bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font: inherit;
  font-size: 13px;
  padding: 6px 8px;
  width: 100%;
}
.input:focus-visible, .btn:focus-visible, button:focus-visible {
  outline: 2px solid var(--text);
  outline-offset: 1px;
}
.input.invalid { border-color: var(--err); }

label { display: block; font-size: 11px; color: var(--muted); margin: 8px 0 2px; }
```

- [ ] **Step 3: main.ts / App.vue 작성**

`server/frontend/src/main.ts`:

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/tokens.css'
import './styles/base.css'
import App from './App.vue'
import router from './router'

createApp(App).use(createPinia()).use(router).mount('#app')
```

`server/frontend/src/App.vue`:

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 4: LoginView 작성**

`server/frontend/src/views/LoginView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await auth.login(password.value)
    router.push('/')
  } catch {
    error.value = '✕ 비밀번호가 올바르지 않습니다'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="wrap">
    <form class="panel" @submit.prevent="submit">
      <h1>E-FAIRBOARD</h1>
      <p class="sub">관리자 로그인</p>
      <label for="pw">비밀번호</label>
      <input id="pw" v-model="password" type="password" class="input" autofocus />
      <p v-if="error" class="err" role="alert">{{ error }}</p>
      <button class="btn btn-primary" type="submit" :disabled="busy || !password">
        {{ busy ? '확인 중…' : '로그인' }}
      </button>
    </form>
  </main>
</template>

<style scoped>
.wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.panel {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 32px; width: 320px; display: flex; flex-direction: column; gap: 4px;
}
h1 { font-size: 16px; letter-spacing: 3px; }
.sub { color: var(--muted); font-size: 12px; margin-bottom: 12px; }
.err { color: var(--err); font-size: 12px; margin-top: 6px; }
.btn { margin-top: 14px; }
</style>
```

- [ ] **Step 5: DashboardView 임시 골격 작성**

`server/frontend/src/views/DashboardView.vue` (Task 5에서 교체된다):

```vue
<template>
  <main style="padding: 24px">대시보드 — Task 5에서 구현</main>
</template>
```

- [ ] **Step 6: 수동 검증 — 로그인 왕복**

터미널 1: `cd server/backend; uvicorn app.main:create_app --factory --port 8000`
터미널 2: `cd server/frontend; npm run dev`

브라우저 http://localhost:5173 → `/login`으로 리다이렉트 → `.env`의 ADMIN_PASSWORD로 로그인 → `/`(임시 골격) 도착. 틀린 비밀번호 → 빨간 에러 문구. 로그아웃은 아직 없음(정상).
Expected: 위 흐름 동작 + 콘솔 에러 없음

- [ ] **Step 7: 타입체크 + 테스트 + 커밋**

Run: `cd server/frontend; npx vue-tsc -b; npm test`
Expected: 타입 에러 없음, 테스트 PASS

```bash
git add server/frontend
git commit -m "feat(frontend): 다크 토큰 · 앱 엔트리 · 로그인 (스펙 §4)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Pinia 스토어 — nodes · posts · deployments

**Files:**
- Create: `server/frontend/src/stores/nodes.ts`, `server/frontend/src/stores/posts.ts`, `server/frontend/src/stores/deployments.ts`

**Interfaces:**
- Consumes: `api` (Task 2), Task 1의 응답 형태 (`NodeInfo.display_state`, `DeployTarget.step_*`)
- Produces:
  - `useNodes()`: `list: Ref<NodeInfo[]>`, `connected: Ref<boolean>`, `virtualMode: Ref<boolean|null>`, `onlineCount: ComputedRef<number>`, `fetch()`, `startPolling(ms=5000)`, `stopPolling()`, `detectMode()`
  - `usePosts()`: `list: Ref<Post[]>`, `templates: Ref<TemplateDef[]>`, `byId: ComputedRef<Map<number, Post>>`, `fetch()`, `fetchTemplates()`, `save(id: number|null, body): Promise<Post>`
  - `useDeployments()`: `byNode: Map<number, {deployment: Deployment, post: Post}>`(reactive), `deployToNode(post: Post, nodeId: number, refreshMode: 0|1)`, `retry(nodeId)`, `dismiss(nodeId)`

- [ ] **Step 1: nodes 스토어 작성**

`server/frontend/src/stores/nodes.ts`:

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, type NodeInfo } from '../api'

export const useNodes = defineStore('nodes', () => {
  const list = ref<NodeInfo[]>([])
  const connected = ref(true)              // 마지막 fetch 성공 여부 — 상단 바 표시
  const virtualMode = ref<boolean | null>(null)   // null = 아직 모름
  let timer: number | undefined

  async function fetch() {
    try {
      list.value = await api.nodes()
      connected.value = true
    } catch {
      connected.value = false               // 401은 인터셉터가 로그인으로 보낸다
    }
  }

  /** GET /api/sim/config 200 → 가상 모드, 409 → 시리얼 모드 (routers/sim.py) */
  async function detectMode() {
    try {
      await api.simConfig()
      virtualMode.value = true
    } catch {
      virtualMode.value = false
    }
  }

  function startPolling(ms = 5000) {
    stopPolling()
    fetch()
    timer = window.setInterval(fetch, ms)
  }
  function stopPolling() {
    if (timer !== undefined) { clearInterval(timer); timer = undefined }
  }

  const onlineCount = computed(() => list.value.filter(n => n.status === 'online').length)

  return { list, connected, virtualMode, onlineCount, fetch, detectMode, startPolling, stopPolling }
})
```

- [ ] **Step 2: posts 스토어 작성**

`server/frontend/src/stores/posts.ts`:

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, type Post } from '../api'
import type { TemplateDef } from '../epaper/types'

type PostBody = Omit<Post, 'id' | 'created_at' | 'updated_at'>

export const usePosts = defineStore('posts', () => {
  const list = ref<Post[]>([])
  const templates = ref<TemplateDef[]>([])

  async function fetch() { list.value = await api.posts() }
  async function fetchTemplates() { templates.value = await api.templates() }

  const byId = computed(() => new Map(list.value.map(p => [p.id, p])))

  /** id=null 이면 생성, 아니면 수정. 저장 후 목록 갱신, 저장된 Post 반환. */
  async function save(id: number | null, body: PostBody): Promise<Post> {
    const saved = id === null ? await api.createPost(body) : await api.updatePost(id, body)
    await fetch()
    return saved
  }

  return { list, templates, byId, fetch, fetchTemplates, save }
})
```

- [ ] **Step 3: deployments 스토어 작성**

`server/frontend/src/stores/deployments.ts`:

```ts
import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { api, type Deployment, type Post } from '../api'
import { useNodes } from './nodes'

export interface NodeDeploy {
  deployment: Deployment
  post: Post          // 진행 오버레이의 단계 목록 렌더용 — 방금 배포한 게시물
}

export const useDeployments = defineStore('deployments', () => {
  /** 노드별 진행/실패 상태. 성공하면 지워지고, 실패는 dismiss/retry 까지 남는다. */
  const byNode = reactive(new Map<number, NodeDeploy>())

  async function deployToNode(post: Post, nodeId: number, refreshMode: 0 | 1) {
    const dep = await api.deploy(post.id, [nodeId], refreshMode)
    byNode.set(nodeId, { deployment: dep, post })
    poll(dep.id, nodeId)
  }

  function poll(depId: number, nodeId: number) {
    const timer = window.setInterval(async () => {
      let dep: Deployment
      try {
        dep = await api.deployment(depId)
      } catch {
        return             // 일시 오류 — 다음 틱에 재시도
      }
      const cur = byNode.get(nodeId)
      if (cur) cur.deployment = dep
      if (dep.status !== 'running') {
        clearInterval(timer)
        await useNodes().fetch()            // 미리보기 즉시 교체 (스펙 §6.2)
        if (dep.status === 'success') byNode.delete(nodeId)
        // 단일 노드 배포라 partial 은 없다 — failed 만 카드에 남는다
      }
    }, 1000)
  }

  async function retry(nodeId: number) {
    const cur = byNode.get(nodeId)
    if (!cur) return
    await deployToNode(cur.post, nodeId, cur.deployment.refresh_mode as 0 | 1)
  }

  function dismiss(nodeId: number) { byNode.delete(nodeId) }

  return { byNode, deployToNode, retry, dismiss }
})
```

- [ ] **Step 4: 타입체크 + 커밋**

Run: `cd server/frontend; npx vue-tsc -b`
Expected: 에러 없음

```bash
git add server/frontend/src/stores
git commit -m "feat(frontend): nodes·posts·deployments 스토어 — 5초/1초 폴링 (스펙 §5)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: AppShell + NodeCard(평상시·오프라인) + DashboardView 조립

**Files:**
- Create: `server/frontend/src/components/AppShell.vue`, `server/frontend/src/components/NodeCard.vue`
- Modify: `server/frontend/src/views/DashboardView.vue` (임시 골격 교체)

**Interfaces:**
- Consumes: `useNodes()`·`usePosts()` (Task 4), `EpaperPreview` (Task 2), 토큰 CSS (Task 3)
- Produces: `NodeCard` props `{ node: NodeInfo }` + emit `edit(node: NodeInfo)` — Task 6이 edit 이벤트에 다이얼로그를 연결, Task 7이 이 카드에 오버레이를 추가

- [ ] **Step 1: AppShell 작성**

`server/frontend/src/components/AppShell.vue`:

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import { useNodes } from '../stores/nodes'

const nodes = useNodes()
const auth = useAuth()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="shell">
    <header>
      <h1>E-FAIRBOARD</h1>
      <div class="status">
        <span v-if="nodes.connected" class="ok">● 서버 연결됨</span>
        <span v-else class="err">○ 서버 응답 없음</span>
        <span v-if="nodes.virtualMode" class="badge">가상 모드</span>
        <span class="muted">온라인 {{ nodes.onlineCount }}/{{ nodes.list.length }}</span>
        <button class="btn" @click="logout">로그아웃</button>
      </div>
    </header>
    <main><slot /></main>
  </div>
</template>

<style scoped>
.shell { max-width: 1280px; margin: 0 auto; padding: 20px 24px; }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
h1 { font-size: 16px; letter-spacing: 3px; }
.status { display: flex; align-items: center; gap: 12px; font-size: 12px; }
.ok { color: var(--ok); }
.err { color: var(--err); }
.muted { color: var(--muted); }
.badge {
  background: var(--panel); border: 1px solid var(--border); border-radius: 4px;
  color: var(--busy); padding: 1px 6px; font-size: 11px;
}
</style>
```

- [ ] **Step 2: NodeCard 작성 (평상시·오프라인 — 배포 오버레이는 Task 7)**

`server/frontend/src/components/NodeCard.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type NodeInfo } from '../api'
import { usePosts } from '../stores/posts'
import EpaperPreview from './EpaperPreview.vue'

const props = defineProps<{ node: NodeInfo }>()
defineEmits<{ edit: [node: NodeInfo] }>()

const posts = usePosts()

/** 스펙 §5 — ×2 기본, 뷰포트 1280px 미만이면 ×1 (정수 배율만) */
const winW = ref(window.innerWidth)
const onResize = () => { winW.value = window.innerWidth }
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))
const previewScale = computed(() => (winW.value < 1280 ? 1 : 2))

const template = computed(() => {
  const tid = props.node.display_state?.template_id
  return tid == null ? null : posts.templates.find(t => t.id === tid) ?? null
})
const currentPost = computed(() =>
  props.node.current_post_id == null ? null : posts.byId.get(props.node.current_post_id) ?? null)
const offline = computed(() => props.node.status !== 'online')

/* ponytail: 리튬 3.3~4.2V 선형 근사 — 실측 방전 곡선 나오면 보정 */
const battPct = computed(() => {
  const mv = props.node.batt_mv
  if (mv == null) return null
  return Math.min(100, Math.max(0, Math.round((mv - 3300) / 9)))
})
const battBar = computed(() =>
  battPct.value == null ? '' : '▮'.repeat(Math.round(battPct.value / 20)).padEnd(5, '▯'))

function timeAgo(iso: string | null): string {
  if (!iso) return '응답 기록 없음'
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}초 전`
  if (s < 3600) return `${Math.floor(s / 60)}분 전`
  return `${Math.floor(s / 3600)}시간 전`
}

const pinging = ref(false)
async function ping() {
  pinging.value = true
  try { await api.ping(props.node.id) } finally { pinging.value = false }
}
</script>

<template>
  <article class="card" :class="{ offline }">
    <div class="screen" :class="{ dim: offline }">
      <EpaperPreview
        :template="template"
        :fields="node.display_state?.fields ?? {}"
        :qr-url="node.display_state?.qr_url ?? ''"
        :scale="previewScale"
      />
      <span v-if="offline" class="dim-label">마지막 커밋 화면</span>
    </div>

    <div class="head">
      <span class="name">NODE 0x{{ node.id.toString(16).padStart(2, '0').toUpperCase() }} · {{ node.name }}</span>
      <span v-if="!offline" class="ok">● ONLINE</span>
      <span v-else class="err">○ OFFLINE</span>
    </div>

    <p class="tele" :class="{ err: offline }">
      <template v-if="battPct != null">BATT {{ ((node.batt_mv ?? 0) / 1000).toFixed(1) }}V {{ battBar }} {{ battPct }}% · </template>
      <template v-if="node.rssi != null">RSSI {{ node.rssi }}dBm · </template>
      {{ offline ? '마지막 응답 ' : '' }}{{ timeAgo(node.last_seen_at) }}
    </p>
    <p class="post muted">
      게시물: {{ currentPost ? `${currentPost.title} #${currentPost.id}` : '없음' }}
    </p>

    <div class="actions">
      <button class="btn btn-primary grow" :disabled="offline" @click="$emit('edit', node)">
        {{ currentPost ? '내용 수정' : '내용 등록' }}
      </button>
      <button class="btn" :disabled="pinging" @click="ping">PING</button>
      <button class="btn" disabled title="다음 설계에서 구현">이력</button>
    </div>
  </article>
</template>

<style scoped>
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px; flex: 1; min-width: 0;
}
.card.offline { border-color: var(--err); }
.screen { position: relative; display: flex; justify-content: center; }
.screen :deep(.epd) { box-shadow: 0 0 16px rgba(255, 255, 255, .12); }
.screen.dim :deep(.epd) { filter: brightness(.45) grayscale(.3); }
.dim-label { position: absolute; top: 6px; right: 6px; font-size: 10px; color: var(--err); }
.head { display: flex; justify-content: space-between; margin-top: 10px; font-size: 13px; }
.ok { color: var(--ok); }
.err { color: var(--err); }
.muted { color: var(--muted); }
.tele { font-size: 12px; color: var(--muted); margin-top: 4px; }
.tele.err { color: var(--err); }
.post { font-size: 12px; margin-top: 2px; }
.actions { display: flex; gap: 8px; margin-top: 10px; }
.grow { flex: 1; }
</style>
```

- [ ] **Step 3: DashboardView 조립**

`server/frontend/src/views/DashboardView.vue` 전체 교체:

```vue
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import AppShell from '../components/AppShell.vue'
import NodeCard from '../components/NodeCard.vue'
import { useNodes } from '../stores/nodes'
import { usePosts } from '../stores/posts'
import type { NodeInfo } from '../api'

const nodes = useNodes()
const posts = usePosts()

onMounted(() => {
  nodes.startPolling(5000)      // 스펙 §5
  nodes.detectMode()
  posts.fetch()
  posts.fetchTemplates()
})
onUnmounted(() => nodes.stopPolling())

function openEdit(_node: NodeInfo) {
  // Task 6 에서 EditDialog 연결
}
</script>

<template>
  <AppShell>
    <div class="grid">
      <NodeCard v-for="n in nodes.list" :key="n.id" :node="n" @edit="openEdit" />
    </div>
  </AppShell>
</template>

<style scoped>
.grid { display: flex; gap: 16px; flex-wrap: wrap; }
</style>
```

- [ ] **Step 4: 수동 검증**

백엔드 + `npm run dev` 실행(Task 3과 동일). 브라우저에서:
1. 카드 2장, 각각 흰 미리보기(내용 없으면 빈 화면)와 `● ONLINE` 초록 표시
2. 임시로 게시물을 배포해 내용 확인: `POST /api/posts` + `POST /api/deployments`를 http://localhost:8000/docs 에서 실행 → 5초 내 카드 미리보기에 텍스트·QR 표시
3. http://localhost:8000/docs 에서 `POST /api/sim/nodes/2/power {"powered": false}` → PING → 카드가 빨간 테두리 `○ OFFLINE` + 어두운 미리보기 + [내용 수정] 비활성으로 전환
Expected: 위 3가지 + 콘솔 에러 없음

- [ ] **Step 5: 타입체크 + 커밋**

Run: `cd server/frontend; npx vue-tsc -b; npm test`
Expected: PASS

```bash
git add server/frontend
git commit -m "feat(frontend): 대시보드 — AppShell·NodeCard, 노드 상태가 주인공 (스펙 §3.1)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: EditDialog — 수정·등록 + 저장=배포

**Files:**
- Create: `server/frontend/src/components/EditDialog.vue`
- Modify: `server/frontend/src/views/DashboardView.vue` (다이얼로그 연결)

**Interfaces:**
- Consumes: `usePosts().save/templates/byId`, `useDeployments().deployToNode` (Task 4), `EpaperPreview`, `epaper/text.ts`의 `clip/scaleFor/utf8Bytes`
- Produces: `EditDialog` props `{ node: NodeInfo }`, emit `close` — 부모가 `v-if`로 마운트하면 즉시 모달로 열린다

- [ ] **Step 1: EditDialog 작성**

`server/frontend/src/components/EditDialog.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { NodeInfo, Post } from '../api'
import { clip, scaleFor, utf8Bytes } from '../epaper/text'
import type { FieldDef } from '../epaper/types'
import { useDeployments } from '../stores/deployments'
import { usePosts } from '../stores/posts'
import EpaperPreview from './EpaperPreview.vue'

const props = defineProps<{ node: NodeInfo }>()
const emit = defineEmits<{ close: [] }>()

const posts = usePosts()
const deployments = useDeployments()
const dialog = ref<HTMLDialogElement | null>(null)
onMounted(() => dialog.value?.showModal())

const QR_MAX_BYTES = 198   // 백엔드 _MAX_TEXT_BYTES 와 동일 (schemas.py)

/** 편집 대상: 노드의 현재 게시물로 시작. 'new' = 새 게시물. */
const currentPost = props.node.current_post_id == null
  ? null : posts.byId.get(props.node.current_post_id) ?? null
const postChoice = ref<number | 'new'>(currentPost?.id ?? 'new')

const form = reactive({
  title: '',
  template_id: 0,
  fields: {} as Record<string, string>,
  qr_url: '',
})

/** 선택이 바뀌면 폼을 그 게시물(또는 빈 값)으로 채운다. */
function loadForm(p: Post | null) {
  form.title = p?.title ?? ''
  form.template_id = p?.template_id ?? posts.templates[0]?.id ?? 0
  form.fields = { ...(p?.fields ?? {}) }
  form.qr_url = p?.qr_url ?? ''
}
loadForm(currentPost)
watch(postChoice, (c) => loadForm(c === 'new' ? null : posts.byId.get(c) ?? null))

const template = computed(() =>
  posts.templates.find(t => t.id === form.template_id) ?? null)

/** max_bytes(UTF-8) 초과 입력은 잘라서 거부 — 백엔드 422 이중 방어의 1차 (스펙 §7) */
function onFieldInput(f: FieldDef, e: Event) {
  const el = e.target as HTMLInputElement
  let v = el.value
  while (utf8Bytes(v) > f.max_bytes) v = v.slice(0, -1)
  if (v !== el.value) el.value = v
  form.fields[String(f.id)] = v
}
function onQrInput(e: Event) {
  const el = e.target as HTMLInputElement
  let v = el.value
  while (utf8Bytes(v) > QR_MAX_BYTES) v = v.slice(0, -1)
  if (v !== el.value) el.value = v
  form.qr_url = v
}

/** 픽셀 폭 초과 필드 id 집합 — 경고만, 저장 차단 없음 (스펙 §3.3) */
const clippedIds = computed(() => {
  const t = template.value
  if (!t) return new Set<number>()
  return new Set(t.fields
    .filter(f => clip(form.fields[String(f.id)] ?? '', f.avail_w, scaleFor(f.font_size)).clipped)
    .map(f => f.id))
})

const refreshMode = ref<0 | 1>(0)
const busy = ref(false)
const error = ref('')

async function save() {
  const t = template.value
  if (!t) return
  busy.value = true
  error.value = ''
  try {
    // 템플릿의 모든 필드를 보낸다 — 빈 값도 전송해야 노드의 이전 텍스트가 지워진다
    const fields: Record<string, string> = {}
    for (const f of t.fields) fields[String(f.id)] = form.fields[String(f.id)] ?? ''
    const body = { title: form.title || t.name, template_id: t.id, fields, qr_url: form.qr_url }
    const saved = await posts.save(postChoice.value === 'new' ? null : postChoice.value, body)
    await deployments.deployToNode(saved, props.node.id, refreshMode.value)
    emit('close')
  } catch (e) {
    error.value = '✕ 저장/배포 요청 실패 — 입력을 확인하세요'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="dlg" @close="emit('close')">
    <div class="head">
      <strong>NODE 0x{{ node.id.toString(16).padStart(2, '0').toUpperCase() }} 내용 {{ currentPost ? '수정' : '등록' }}</strong>
      <button class="btn" @click="emit('close')">✕</button>
    </div>

    <div class="cols">
      <div class="form">
        <label for="post">게시물</label>
        <select id="post" v-model="postChoice" class="input">
          <option v-for="p in posts.list" :key="p.id" :value="p.id">{{ p.title }} #{{ p.id }}</option>
          <option value="new">+ 새로 만들기</option>
        </select>

        <label for="title">게시물 이름</label>
        <input id="title" v-model="form.title" class="input" :placeholder="template?.name" />

        <label for="tpl">템플릿</label>
        <select id="tpl" v-model.number="form.template_id" class="input">
          <option v-for="t in posts.templates" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>

        <template v-for="f in template?.fields ?? []" :key="f.id">
          <label :for="`f${f.id}`">{{ f.name }}</label>
          <input
            :id="`f${f.id}`" class="input" :class="{ invalid: clippedIds.has(f.id) }"
            :value="form.fields[String(f.id)] ?? ''" @input="onFieldInput(f, $event)"
          />
          <p v-if="clippedIds.has(f.id)" class="warn" role="alert">⚠ 화면에서 잘립니다 (픽셀 폭 초과)</p>
        </template>

        <label for="qr">QR URL</label>
        <input id="qr" :value="form.qr_url" class="input" @input="onQrInput" />
      </div>

      <div class="side">
        <label>라이브 미리보기 (296×128)</label>
        <EpaperPreview :template="template" :fields="form.fields" :qr-url="form.qr_url" :scale="1" />
        <label>갱신 방식</label>
        <div class="radios">
          <label class="radio"><input v-model.number="refreshMode" type="radio" :value="0" /> 부분(빠름)</label>
          <label class="radio"><input v-model.number="refreshMode" type="radio" :value="1" /> 전체(잔상 제거)</label>
        </div>
      </div>
    </div>

    <p v-if="error" class="warn" role="alert">{{ error }}</p>
    <div class="foot">
      <button class="btn" :disabled="busy" @click="emit('close')">취소</button>
      <button class="btn btn-primary" :disabled="busy || !template" @click="save">
        {{ busy ? '요청 중…' : '저장하고 이 노드에 배포' }}
      </button>
    </div>
  </dialog>
</template>

<style scoped>
.dlg {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  color: var(--text); padding: 16px; width: 640px; max-width: 90vw;
}
.dlg::backdrop { background: rgba(14, 17, 22, .8); }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cols { display: flex; gap: 16px; }
.form { flex: 1; min-width: 0; }
.side { width: 300px; }
.warn { color: var(--err); font-size: 11px; margin-top: 2px; }
.radios { display: flex; gap: 12px; font-size: 12px; }
.radio { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text); margin: 0; }
.foot {
  display: flex; justify-content: flex-end; gap: 8px;
  border-top: 1px solid var(--border); margin-top: 14px; padding-top: 12px;
}
</style>
```

- [ ] **Step 2: DashboardView에 연결**

`server/frontend/src/views/DashboardView.vue`의 script에서 `openEdit`를 교체하고 다이얼로그를 렌더:

```ts
// 기존 vue import 에 ref 추가: import { onMounted, onUnmounted, ref } from 'vue'
import EditDialog from '../components/EditDialog.vue'

const editing = ref<NodeInfo | null>(null)
function openEdit(node: NodeInfo) { editing.value = node }   // Task 5 의 빈 함수를 교체
```

template의 `</AppShell>` 직전(grid 아래)에 추가:

```html
    <EditDialog v-if="editing" :node="editing" @close="editing = null" />
```

- [ ] **Step 3: 수동 검증 — 수정→배포 E2E**

백엔드 + dev 서버 실행. 브라우저에서:
1. 온라인 노드의 [내용 수정] → 다이얼로그: 현재 게시물이 채워져 있고 우측 미리보기 일치
2. 제목 필드에 긴 영문(예: `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`) 입력 → 빨간 테두리 + "⚠ 화면에서 잘립니다" + 미리보기도 잘림
3. 필드 수정 → [저장하고 이 노드에 배포] → 다이얼로그 닫힘 → 몇 초 내 카드 미리보기가 새 내용으로 교체
4. [+ 새로 만들기] 선택 → 빈 폼 → 저장 → 새 게시물로 배포됨
Expected: 위 4가지 + 콘솔 에러 없음

- [ ] **Step 4: 타입체크 + 커밋**

Run: `cd server/frontend; npx vue-tsc -b; npm test`
Expected: PASS

```bash
git add server/frontend
git commit -m "feat(frontend): EditDialog — 카드에서 바로 수정·등록, 저장=배포 (스펙 §3.3)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: 배포 진행 오버레이 — 카드가 진행판이 된다

**Files:**
- Create: `server/frontend/src/components/DeployOverlay.vue`
- Modify: `server/frontend/src/components/NodeCard.vue` (오버레이·배포 중 상태 연결)

**Interfaces:**
- Consumes: `useDeployments().byNode/retry/dismiss` (Task 4), `DeployTarget.step_*` (Task 1·2)
- Produces: 완성된 NodeCard — 이후 태스크 없음

- [ ] **Step 1: DeployOverlay 작성**

`server/frontend/src/components/DeployOverlay.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { NodeDeploy } from '../stores/deployments'

const props = defineProps<{ nd: NodeDeploy }>()
defineEmits<{ retry: [], dismiss: [] }>()

const target = computed(() => props.nd.deployment.targets[0])
const failed = computed(() => props.nd.deployment.status === 'failed')

/** 단계 목록 — build_packet_plan 과 같은 순서 (deploy_service.py §4) */
const steps = computed(() => {
  const p = props.nd.post
  const n = Object.keys(p.fields).length
  const s = ['SET_TEMPLATE']
  for (let i = 1; i <= n; i++) s.push(`SET_FIELD ${i}/${n}`)
  if (p.qr_url) s.push('SET_QR')
  s.push('COMMIT')
  return s
})
const cur = computed(() => target.value.step_index)   // 1-base, 0=시작 전
const pct = computed(() =>
  target.value.step_total ? Math.round((cur.value / target.value.step_total) * 100) : 0)
</script>

<template>
  <div class="overlay" role="status">
    <template v-if="!failed">
      <p v-for="(s, i) in steps" :key="s"
         :class="i + 1 < cur ? 'done' : i + 1 === cur ? 'now' : 'todo'">
        {{ i + 1 < cur ? '✓' : i + 1 === cur ? '▶' : '·' }} {{ s }}
      </p>
    </template>
    <template v-else>
      <p class="fail">✕ 실패 — {{ target.step_name }} {{ target.step_index }}/{{ target.step_total }}에서 중단</p>
      <p class="reason">{{ target.error }}</p>
      <div class="acts">
        <button class="btn" @click="$emit('dismiss')">닫기</button>
        <button class="btn btn-primary" @click="$emit('retry')">재시도</button>
      </div>
    </template>
  </div>
  <div v-if="!failed" class="bar"><div class="fill" :style="{ width: pct + '%' }" /></div>
</template>

<style scoped>
.overlay {
  position: absolute; inset: 0; background: rgba(14, 17, 22, .85);
  display: flex; flex-direction: column; justify-content: center;
  padding: 12px; font-size: 12px; gap: 2px;
}
.done { color: var(--ok); }
.now { color: var(--busy); }
.todo { color: var(--muted); }
.fail { color: var(--err); font-weight: 600; }
.reason { color: var(--muted); font-size: 11px; word-break: break-all; }
.acts { display: flex; gap: 8px; margin-top: 8px; }
.bar { background: var(--border); border-radius: 3px; height: 6px; margin-top: 8px; overflow: hidden; }
.fill { background: var(--busy); height: 100%; transition: width .3s; }
</style>
```

- [ ] **Step 2: NodeCard에 연결**

`server/frontend/src/components/NodeCard.vue` script에 추가:

```ts
import { useDeployments } from '../stores/deployments'
import DeployOverlay from './DeployOverlay.vue'

const deployments = useDeployments()
const deploy = computed(() => deployments.byNode.get(props.node.id))
const deploying = computed(() => deploy.value?.deployment.status === 'running')
const deployFailed = computed(() => deploy.value?.deployment.status === 'failed')
```

template 수정 3곳:

1. `.screen` div 안, `EpaperPreview` 아래에 오버레이 추가:

```html
      <DeployOverlay
        v-if="deploy" :nd="deploy"
        @retry="deployments.retry(node.id)"
        @dismiss="deployments.dismiss(node.id)"
      />
```

2. `.head`의 상태 표시를 배포 상태 우선으로 교체:

```html
      <span v-if="deploying" class="busy">◈ 배포 중</span>
      <span v-else-if="deployFailed" class="err">✕ 실패</span>
      <span v-else-if="!offline" class="ok">● ONLINE</span>
      <span v-else class="err">○ OFFLINE</span>
```

3. `<article>`의 class 바인딩과 [내용 수정] 버튼 disabled 갱신:

```html
  <article class="card" :class="{ offline: offline && !deploying, busy: deploying }">
```

```html
      <button class="btn btn-primary grow" :disabled="offline || deploying" @click="$emit('edit', node)">
```

style에 추가:

```css
.card.busy { border-color: var(--busy); }
.busy { color: var(--busy); }
```

- [ ] **Step 3: 수동 검증 — 진행·실패·재시도**

백엔드 + dev 서버 실행:
1. http://localhost:8000/docs 에서 `PUT /api/sim/config {"airtime_s": 0.8}` — 전송을 느리게 해 단계가 보이게
2. [내용 수정] → 저장 → 카드가 호박 테두리 `◈ 배포 중`, 오버레이에 단계가 ✓/▶로 진행, 진행바 증가
3. 완료 순간 오버레이 걷힘 + 미리보기 즉시 교체
4. `POST /api/sim/nodes/1/power {"powered": false}` → 노드1에 배포 → 십수 초 후 `✕ 실패 — …에서 중단` + error 문구 + [재시도][닫기]
5. `{"powered": true}` 복구 → [재시도] → 성공
Expected: 위 5가지 + 콘솔 에러 없음

- [ ] **Step 4: 타입체크 + 커밋**

Run: `cd server/frontend; npx vue-tsc -b; npm test`
Expected: PASS

```bash
git add server/frontend
git commit -m "feat(frontend): 배포 진행 오버레이 — 단계·진행바·실패/재시도 (스펙 §3.2)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: 빌드 · 단일 프로세스 서빙 · 전체 회귀 확인

**Files:**
- 없음 (검증 태스크 — 산출물은 `server/frontend/dist/`, gitignore 대상)

**Interfaces:**
- Consumes: 전체 결과물
- Produces: 완료 판정

- [ ] **Step 1: 프론트 프로덕션 빌드**

Run: `cd server/frontend; npm run build`
Expected: `vue-tsc -b` 에러 없음, `dist/` 생성

- [ ] **Step 2: 단일 프로세스 서빙 확인 (스펙 §4 실행 모델)**

dev 서버는 끄고 백엔드만 실행: `cd server/backend; uvicorn app.main:create_app --factory --port 8000`
브라우저 http://localhost:8000 → 로그인 → 대시보드 전체 동작(카드·수정·배포) 확인.
Expected: Vite 없이 8000 포트 단독으로 동일하게 동작

- [ ] **Step 3: 전체 테스트 회귀**

Run: `cd server/backend; python -m pytest -q` 그리고 `cd server/frontend; npm test`
Expected: 전부 PASS

- [ ] **Step 4: 남은 변경이 있으면 커밋**

```bash
git status --short   # 깨끗해야 정상 — dist/ 는 .gitignore 에 걸러진다
```

Expected: 추적되는 변경 없음 (있다면 앞 태스크에서 누락된 것 — 원인 확인 후 커밋)
