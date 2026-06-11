<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card>
          <template #header><span>策略选择与配置</span></template>

          <div style="margin-bottom: 16px;">
            <h4>收益矩阵 (对称博弈):</h4>
            <p style="font-size: 12px; color: #909399; margin: 0 0 8px 0;">每格填写该玩家的收益，对称博弈中双方使用相同矩阵</p>
            <table class="payoff-table">
              <thead>
                <tr>
                  <th class="corner-cell">我 ＼ 对手</th>
                  <th class="header-cell">合作 (C)</th>
                  <th class="header-cell">背叛 (D)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="row-header"><strong>合作 (C)</strong></td>
                  <td class="payoff-cell">
                    <el-input-number v-model="payoffCC" size="small" :controls="false" style="width: 70px;" />
                    <span class="payoff-hint">, {{ payoffCC }}</span>
                  </td>
                  <td class="payoff-cell">
                    <el-input-number v-model="payoffCD" size="small" :controls="false" style="width: 70px;" />
                    <span class="payoff-hint">, {{ payoffDC }}</span>
                  </td>
                </tr>
                <tr>
                  <td class="row-header"><strong>背叛 (D)</strong></td>
                  <td class="payoff-cell">
                    <el-input-number v-model="payoffDC" size="small" :controls="false" style="width: 70px;" />
                    <span class="payoff-hint">, {{ payoffCD }}</span>
                  </td>
                  <td class="payoff-cell">
                    <el-input-number v-model="payoffDD" size="small" :controls="false" style="width: 70px;" />
                    <span class="payoff-hint">, {{ payoffDD }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div style="margin-top: 8px; display: flex; gap: 4px; flex-wrap: wrap;">
              <el-button size="small" text type="primary" @click="loadPDPreset('pd')">囚徒困境</el-button>
              <el-button size="small" text type="primary" @click="loadPDPreset('chicken')">胆小鬼博弈</el-button>
              <el-button size="small" text type="primary" @click="loadPDPreset('stag')">猎鹿博弈</el-button>
              <el-button size="small" text type="primary" @click="loadPDPreset('harmony')">和谐博弈</el-button>
            </div>
          </div>

          <div style="margin-bottom: 16px;">
            <h4>选择参与策略:</h4>
            <el-checkbox-group v-model="selectedStrategies">
              <el-checkbox
                v-for="s in strategies"
                :key="s.id"
                :label="s.id"
                :value="s.id"
                style="display: block; margin: 8px 0;"
              >
                <strong>{{ s.name }}</strong>
                <div style="font-size: 12px; color: #909399;">{{ s.description }}</div>
              </el-checkbox>
            </el-checkbox-group>
          </div>

          <div style="margin-bottom: 16px;">
            <h4>博弈轮数:</h4>
            <el-slider v-model="rounds" :min="10" :max="500" :step="10" show-input />
          </div>

          <el-button
            type="primary"
            @click="runTournament"
            :loading="loading"
            :disabled="selectedStrategies.length < 2"
            style="width: 100%;"
          >
            运行锦标赛
          </el-button>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card v-if="result">
          <template #header><span>锦标赛结果排名</span></template>
          <div ref="rankChart" style="width: 100%; height: 250px;"></div>
        </el-card>

        <el-card v-if="result" style="margin-top: 20px;">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>对局详情</span>
              <el-select v-model="selectedMatch" placeholder="选择对局" style="width: 280px;">
                <el-option
                  v-for="(m, idx) in result.matches"
                  :key="idx"
                  :label="getMatchLabel(m)"
                  :value="idx"
                />
              </el-select>
            </div>
          </template>

          <div v-if="selectedMatch !== null" ref="matchChart" style="width: 100%; height: 300px;"></div>

          <div v-if="selectedMatch !== null" style="margin-top: 16px;">
            <h4>逐轮回放</h4>
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 12px;">
              <el-button size="small" @click="startReplay" :disabled="replaying">播放</el-button>
              <el-button size="small" @click="stopReplay">停止</el-button>
              <el-slider v-model="replaySpeed" :min="1" :max="50" style="width: 150px;" />
              <span style="font-size: 12px;">速度: {{ replaySpeed }}x</span>
            </div>
            <div class="replay-grid" v-if="currentRound > 0">
              <div class="round-display">
                <span>第 {{ currentRound }} 轮</span>
                <div class="actions">
                  <el-tag :type="currentAction1 === 'C' ? 'success' : 'danger'">
                    {{ strategyName(currentMatch.strategy1) }}: {{ currentAction1 === 'C' ? '合作' : '背叛' }}
                  </el-tag>
                  <el-tag :type="currentAction2 === 'C' ? 'success' : 'danger'">
                    {{ strategyName(currentMatch.strategy2) }}: {{ currentAction2 === 'C' ? '合作' : '背叛' }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, onUnmounted } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'

const strategies = ref([])
const selectedStrategies = ref(['tit_for_tat', 'always_cooperate', 'always_defect', 'random'])
const rounds = ref(100)
const loading = ref(false)
const result = ref(null)
const selectedMatch = ref(null)
const rankChart = ref(null)
const matchChart = ref(null)
let rankChartInstance = null
let matchChartInstance = null

const payoffCC = ref(3)
const payoffCD = ref(0)
const payoffDC = ref(5)
const payoffDD = ref(1)

function loadPDPreset(type) {
  if (type === 'pd') { payoffCC.value = 3; payoffCD.value = 0; payoffDC.value = 5; payoffDD.value = 1 }
  else if (type === 'chicken') { payoffCC.value = 3; payoffCD.value = 1; payoffDC.value = 5; payoffDD.value = 0 }
  else if (type === 'stag') { payoffCC.value = 4; payoffCD.value = 0; payoffDC.value = 3; payoffDD.value = 3 }
  else if (type === 'harmony') { payoffCC.value = 4; payoffCD.value = 3; payoffDC.value = 2; payoffDD.value = 1 }
}

const replaying = ref(false)
const replaySpeed = ref(10)
const currentRound = ref(0)
const currentAction1 = ref('')
const currentAction2 = ref('')
let replayTimer = null

const currentMatch = ref(null)

const STRATEGY_NAMES = {
  tit_for_tat: '以牙还牙',
  always_cooperate: '始终合作',
  always_defect: '始终背叛',
  random: '随机',
  grudger: '冷酷触发',
  tit_for_two_tats: '宽容以牙还牙',
}

function strategyName(id) {
  return STRATEGY_NAMES[id] || id
}

function getMatchLabel(m) {
  return `${strategyName(m.strategy1)} vs ${strategyName(m.strategy2)}`
}

async function runTournament() {
  loading.value = true
  try {
    const resp = await axios.post('/api/repeated-game/simulate', {
      rounds: rounds.value,
      strategies: selectedStrategies.value,
      payoff_matrix: [
        [payoffCC.value, payoffCD.value],
        [payoffDC.value, payoffDD.value],
      ],
    })
    result.value = resp.data
    selectedMatch.value = null
    await nextTick()
    renderRankChart()
  } catch (e) {
    ElMessage.error('模拟失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function renderRankChart() {
  if (!rankChart.value || !result.value) return
  if (rankChartInstance) rankChartInstance.dispose()
  rankChartInstance = echarts.init(rankChart.value)

  const ranking = result.value.ranking
  rankChartInstance.setOption({
    title: { text: '累计得分排名', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: ranking.map(r => r.name),
      axisLabel: { rotate: 0 }
    },
    yAxis: { type: 'value', name: '总分' },
    series: [{
      type: 'bar',
      data: ranking.map(r => r.score),
      itemStyle: {
        color: (params) => {
          const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
          return colors[params.dataIndex % colors.length]
        }
      },
      label: { show: true, position: 'top', formatter: '{c}' }
    }]
  })
}

watch(selectedMatch, async (val) => {
  if (val === null) return
  currentMatch.value = result.value.matches[val]
  stopReplay()
  currentRound.value = 0
  await nextTick()
  renderMatchChart()
})

function renderMatchChart() {
  if (!matchChart.value || !currentMatch.value) return
  if (matchChartInstance) matchChartInstance.dispose()
  matchChartInstance = echarts.init(matchChart.value)

  const details = currentMatch.value.round_details
  matchChartInstance.setOption({
    title: { text: '累计收益变化', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: [strategyName(currentMatch.value.strategy1), strategyName(currentMatch.value.strategy2)], bottom: 0 },
    xAxis: { type: 'category', data: details.map(d => d.round), name: '轮次' },
    yAxis: { type: 'value', name: '累计收益' },
    series: [
      {
        name: strategyName(currentMatch.value.strategy1),
        type: 'line',
        data: details.map(d => d.cumulative1),
        smooth: true,
        lineStyle: { width: 2 }
      },
      {
        name: strategyName(currentMatch.value.strategy2),
        type: 'line',
        data: details.map(d => d.cumulative2),
        smooth: true,
        lineStyle: { width: 2 }
      }
    ]
  })
}

function startReplay() {
  if (!currentMatch.value) return
  replaying.value = true
  currentRound.value = 0
  replayTimer = setInterval(() => {
    if (currentRound.value >= currentMatch.value.round_details.length) {
      stopReplay()
      return
    }
    const detail = currentMatch.value.round_details[currentRound.value]
    currentAction1.value = detail.action1
    currentAction2.value = detail.action2
    currentRound.value++
  }, 1000 / replaySpeed.value)
}

function stopReplay() {
  replaying.value = false
  if (replayTimer) {
    clearInterval(replayTimer)
    replayTimer = null
  }
}

onMounted(async () => {
  try {
    const resp = await axios.get('/api/repeated-game/strategies')
    strategies.value = resp.data
  } catch (e) {
    console.error(e)
  }
})

onUnmounted(() => {
  stopReplay()
})
</script>

<style scoped>
.replay-grid {
  background: #fafafa;
  padding: 16px;
  border-radius: 8px;
}
.round-display {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 16px;
}
.actions {
  display: flex;
  gap: 12px;
}
.payoff-table {
  border-collapse: collapse;
  width: 100%;
}
.payoff-table th,
.payoff-table td {
  border: 1px solid #dcdfe6;
  padding: 10px 8px;
  text-align: center;
}
.corner-cell {
  background: #f5f7fa;
  font-size: 12px;
  color: #606266;
  width: 90px;
}
.header-cell {
  background: #ecf5ff;
  font-weight: bold;
  color: #409eff;
}
.row-header {
  background: #fdf6ec;
  color: #e6a23c;
  width: 90px;
}
.payoff-cell {
  background: #fff;
}
.payoff-hint {
  color: #909399;
  font-size: 12px;
}
</style>
