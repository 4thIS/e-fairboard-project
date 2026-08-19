<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type SerialPort, type RadioRegisters, type RadioWriteResult } from '../api'
import { errorMessage } from '../api/client'

const HW_MIN = 850, HW_MAX = 930.125   // E22-900: 850.125 + 채널(0~80)
const KR_LO = 920.9, KR_HI = 923.3

const ports = ref<SerialPort[]>([])
const port = ref('')
const registers = ref<RadioRegisters | null>(null)   // 직전 읽기 성공값 = 설정모드 확인 = 쓰기 인터록
const readHint = ref('')                              // 설정모드 아님 안내
const targetMhz = ref(922.125)   // KR920 채널 72 (E22 실제 표기)
const writeResult = ref<RadioWriteResult | null>(null)
const message = ref('')
const busy = ref(false)
const confirming = ref(false)

const mhzValid = computed(() => Number.isFinite(targetMhz.value)
  && targetMhz.value >= HW_MIN && targetMhz.value <= HW_MAX)
const outsideKr = computed(() => mhzValid.value
  && (targetMhz.value < KR_LO || targetMhz.value > KR_HI))
// 쓰기 인터록: 이 포트에서 읽기 성공(설정모드 확인) + 입력 유효할 때만
const canWrite = computed(() => !!registers.value && mhzValid.value && !busy.value)

async function loadPorts() {
  try {
    ports.value = await api.radioPorts()
    if (!port.value && ports.value.length) port.value = ports.value[0].device
  } catch (e) {
    message.value = errorMessage(e, '로그인이 필요합니다')
  }
}

function onPortChange() {   // 포트 바뀌면 이전 읽기 무효 → 인터록 리셋
  registers.value = null
  readHint.value = ''
  writeResult.value = null
}

async function read() {
  if (!port.value) { message.value = '✕ 포트를 선택하세요'; return }
  busy.value = true; message.value = ''; readHint.value = ''; writeResult.value = null
  try {
    const r = await api.radioRead(port.value)
    if (r.ok && r.registers) {
      registers.value = r.registers
      message.value = '✓ 현재 설정을 읽었습니다 (설정 모드)'
    } else {
      registers.value = null
      readHint.value = r.hint ?? '읽기에 실패했습니다'
    }
  } catch (e) {
    registers.value = null
    message.value = errorMessage(e, '로그인이 필요합니다')
  } finally {
    busy.value = false
  }
}

async function write() {
  confirming.value = false
  busy.value = true; message.value = ''
  try {
    const r = await api.radioSetFrequency(port.value, targetMhz.value)
    writeResult.value = r
    if (r.ok) {
      registers.value = r.after ?? registers.value
      message.value = `✓ ${targetMhz.value}MHz 로 설정 완료`
    } else {
      message.value = `✕ ${r.hint ?? '쓰기 실패 — 재시도하세요'}`
    }
  } catch (e) {
    message.value = errorMessage(e, '로그인이 필요합니다')
  } finally {
    busy.value = false
  }
}

onMounted(loadPorts)
</script>

<template>
  <div class="wrap">
    <header>
      <h1>무선 설정 — PC HAT 주파수</h1>
      <router-link class="btn" to="/">← 대시보드</router-link>
    </header>

    <!-- 상시 안내: 3단계 + KR920 -->
    <div class="banner">
      <strong>브링업 절차:</strong>
      ① <b>M1 점퍼 빼기</b>(설정 모드) → ② 주파수 쓰기 → ③ <b>M1 다시 꽂기</b>(전송 모드).
      국내 KR920 권장 범위 <b>920.9 ~ 923.3 MHz</b>. PC·모든 노드가 <b>같은 채널</b>이어야 통신됩니다.
    </div>

    <section class="panel">
      <h2>1. 포트</h2>
      <div class="row">
        <select class="input" v-model="port" @change="onPortChange">
          <option v-if="!ports.length" value="">(포트 없음)</option>
          <option v-for="p in ports" :key="p.device" :value="p.device">
            {{ p.device }}{{ p.description ? ' — ' + p.description : '' }}
          </option>
        </select>
        <button class="btn" :disabled="busy" @click="loadPorts">새로고침</button>
      </div>
    </section>

    <section class="panel">
      <h2>2. 현재 설정 읽기</h2>
      <button class="btn" :disabled="busy || !port" @click="read">현재 설정 읽기</button>

      <div v-if="readHint" class="hint">⚠ {{ readHint }}</div>

      <table v-if="registers" class="reg">
        <tbody>
          <tr><th>주파수</th><td>{{ registers.freq_mhz }} MHz (채널 {{ registers.channel }})</td></tr>
          <tr><th>공중 속도</th><td>{{ registers.air_bps }} bps</td></tr>
          <tr><th>UART</th><td>{{ registers.uart_bps }} bps</td></tr>
          <tr><th>송신 출력</th><td>{{ registers.power_dbm }} dBm</td></tr>
          <tr><th>주소 / NETID</th><td>{{ registers.address }} / {{ registers.netid }}</td></tr>
          <tr><th>raw</th><td class="mono">{{ registers.raw }}</td></tr>
        </tbody>
      </table>
    </section>

    <section class="panel">
      <h2>3. 목표 주파수 쓰기</h2>
      <label for="mhz">목표 주파수 (MHz)</label>
      <div class="row">
        <input id="mhz" class="input" :class="{ invalid: !mhzValid }" type="number"
               v-model.number="targetMhz" :min="HW_MIN" :max="HW_MAX" step="0.125" />
        <button class="btn btn-primary" :disabled="!canWrite" @click="confirming = true">
          설정 쓰기
        </button>
      </div>
      <div v-if="!mhzValid" class="hint">✕ {{ HW_MIN }}~{{ HW_MAX }} MHz 범위로 입력하세요</div>
      <div v-else-if="outsideKr" class="warn">⚠ KR920(920.9~923.3) 범위 밖입니다 — 브링업 용도로만</div>
      <div v-if="!registers" class="muted-note">먼저 “현재 설정 읽기”가 성공해야(설정 모드 확인) 쓰기가 활성화됩니다.</div>

      <div v-if="writeResult && writeResult.before && writeResult.after" class="diff">
        <span>{{ writeResult.before.freq_mhz }} MHz</span>
        <span class="arrow">→</span>
        <span :class="writeResult.ok ? 'ok' : 'err'">{{ writeResult.after.freq_mhz }} MHz</span>
        <span v-if="writeResult.ok" class="ok">검증 일치 ✓</span>
        <span v-else class="err">검증 불일치 ✕</span>
      </div>
    </section>

    <p v-if="message" class="message"
       :class="{ ok: message.startsWith('✓'), err: message.startsWith('✕') }">{{ message }}</p>

    <!-- 쓰기 확인 다이얼로그 -->
    <div v-if="confirming" class="modal-back" @click.self="confirming = false">
      <div class="modal">
        <p>⚠ <b>{{ targetMhz }} MHz</b> 로 씁니다.</p>
        <p class="muted-note">PC와 <b>모든 노드가 같은 채널</b>이어야 통신됩니다. 계속할까요?</p>
        <div class="row end">
          <button class="btn" @click="confirming = false">취소</button>
          <button class="btn btn-primary" @click="write">쓰기</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 640px; margin: 0 auto; padding: 20px 24px; }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
h1 { font-size: 15px; letter-spacing: 1px; }
h2 { font-size: 13px; color: var(--muted); margin-bottom: 10px; }
a.btn { text-decoration: none; }
.banner {
  background: var(--panel); border: 1px solid var(--border); border-left: 3px solid var(--busy);
  border-radius: 6px; padding: 10px 12px; font-size: 12px; line-height: 1.7; margin-bottom: 16px;
}
.panel {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px; margin-bottom: 14px;
}
.row { display: flex; gap: 8px; align-items: center; }
.row.end { justify-content: flex-end; margin-top: 14px; }
.hint { color: var(--err); font-size: 12px; margin-top: 10px; }
.warn { color: var(--busy); font-size: 12px; margin-top: 8px; }
.muted-note { color: var(--muted); font-size: 11px; margin-top: 8px; }
.reg { width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 13px; }
.reg th { text-align: left; color: var(--muted); font-weight: 400; padding: 4px 8px 4px 0; width: 110px; }
.reg td { padding: 4px 0; }
.mono { font-family: var(--mono); color: var(--muted); }
.diff { display: flex; gap: 10px; align-items: center; margin-top: 14px; font-size: 14px; }
.arrow { color: var(--muted); }
.ok { color: var(--ok); }
.err { color: var(--err); }
.message { margin-top: 6px; font-size: 13px; }
.modal-back {
  position: fixed; inset: 0; background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
}
.modal {
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  padding: 20px; width: 340px; font-size: 13px; line-height: 1.6;
}
</style>
