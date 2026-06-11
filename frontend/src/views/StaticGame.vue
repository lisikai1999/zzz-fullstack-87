<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>收益矩阵编辑器</span>
              <el-select v-model="selectedPreset" placeholder="选择预设博弈" @change="loadPreset" style="width: 180px;">
                <el-option v-for="p in presets" :key="p.name" :label="p.name" :value="p.name" />
              </el-select>
            </div>
          </template>

          <div style="margin-bottom: 16px;">
            <el-row :gutter="10" align="middle">
              <el-col :span="6">
                <span>玩家1策略数:</span>
              </el-col>
              <el-col :span="6">
                <el-input-number v-model="rows" :min="2" :max="5" size="small" @change="resizeMatrix" />
              </el-col>
              <el-col :span="6">
                <span>玩家2策略数:</span>
              </el-col>
              <el-col :span="6">
                <el-input-number v-model="cols" :min="2" :max="5" size="small" @change="resizeMatrix" />
              </el-col>
            </el-row>
          </div>

          <div style="overflow-x: auto;">
            <table class="payoff-table">
              <thead>
                <tr>
                  <th></th>
                  <th v-for="(_, j) in cols" :key="j">
                    <el-input v-model="p2Names[j]" size="small" :placeholder="'策略' + (j+1)" />
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(_, i) in rows" :key="i">
                  <td>
                    <el-input v-model="p1Names[i]" size="small" :placeholder="'策略' + (i+1)" style="width: 70px;" />
                  </td>
                  <td v-for="(__, j) in cols" :key="j">
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <el-input-number
                        v-model="matrix1[i][j]"
                        size="small"
                        :controls="false"
                        style="width: 60px;"
                      />
                      <span>,</span>
                      <el-input-number
                        v-model="matrix2[i][j]"
                        size="small"
                        :controls="false"
                        style="width: 60px;"
                      />
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <el-button type="primary" @click="solve" :loading="loading" style="margin-top: 16px; width: 100%;">
            求解纳什均衡
          </el-button>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card v-if="result">
          <template #header><span>求解结果</span></template>

          <div v-if="result.pure_nash.length > 0">
            <h4>纯策略纳什均衡</h4>
            <el-tag
              v-for="(eq, idx) in result.pure_nash"
              :key="idx"
              type="success"
              style="margin: 4px;"
              size="large"
            >
              ({{ getStrategyName(1, eq.player1_strategy) }}, {{ getStrategyName(2, eq.player2_strategy) }})
              → 收益: ({{ eq.player1_payoff }}, {{ eq.player2_payoff }})
            </el-tag>
          </div>
          <div v-else>
            <el-alert title="不存在纯策略纳什均衡" type="info" :closable="false" />
          </div>

          <div v-if="result.mixed_nash" style="margin-top: 16px;">
            <h4>混合策略纳什均衡</h4>
            <div style="background: #f0f9eb; padding: 12px; border-radius: 4px;">
              <p><strong>玩家1混合策略:</strong>
                <span v-for="(prob, idx) in result.mixed_nash.player1_probs" :key="'p1-'+idx">
                  {{ getStrategyName(1, idx) }}: {{ (prob * 100).toFixed(1) }}%
                  <span v-if="idx < result.mixed_nash.player1_probs.length - 1"> | </span>
                </span>
              </p>
              <p><strong>玩家2混合策略:</strong>
                <span v-for="(prob, idx) in result.mixed_nash.player2_probs" :key="'p2-'+idx">
                  {{ getStrategyName(2, idx) }}: {{ (prob * 100).toFixed(1) }}%
                  <span v-if="idx < result.mixed_nash.player2_probs.length - 1"> | </span>
                </span>
              </p>
              <p><strong>期望收益:</strong>
                玩家1: {{ result.mixed_nash.player1_expected_payoff.toFixed(3) }} |
                玩家2: {{ result.mixed_nash.player2_expected_payoff.toFixed(3) }}
              </p>
            </div>
          </div>
        </el-card>

        <el-card v-if="result && result.best_response_data" style="margin-top: 20px;">
          <template #header><span>最优响应函数图</span></template>
          <div ref="brChart" style="width: 100%; height: 400px;"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'

const rows = ref(2)
const cols = ref(2)
const matrix1 = ref([[-1, -3], [0, -2]])
const matrix2 = ref([[-1, 0], [-3, -2]])
const p1Names = ref(['合作', '背叛'])
const p2Names = ref(['合作', '背叛'])
const presets = ref([])
const selectedPreset = ref('')
const loading = ref(false)
const result = ref(null)
const brChart = ref(null)
let chartInstance = null

function resizeMatrix() {
  const r = rows.value
  const c = cols.value
  while (matrix1.value.length < r) matrix1.value.push(new Array(c).fill(0))
  while (matrix1.value.length > r) matrix1.value.pop()
  while (matrix2.value.length < r) matrix2.value.push(new Array(c).fill(0))
  while (matrix2.value.length > r) matrix2.value.pop()
  for (let i = 0; i < r; i++) {
    while (matrix1.value[i].length < c) matrix1.value[i].push(0)
    while (matrix1.value[i].length > c) matrix1.value[i].pop()
    while (matrix2.value[i].length < c) matrix2.value[i].push(0)
    while (matrix2.value[i].length > c) matrix2.value[i].pop()
  }
  while (p1Names.value.length < r) p1Names.value.push('')
  while (p1Names.value.length > r) p1Names.value.pop()
  while (p2Names.value.length < c) p2Names.value.push('')
  while (p2Names.value.length > c) p2Names.value.pop()
}

function loadPreset(name) {
  const p = presets.value.find(x => x.name === name)
  if (!p) return
  rows.value = p.player1_matrix.length
  cols.value = p.player1_matrix[0].length
  matrix1.value = p.player1_matrix.map(r => [...r])
  matrix2.value = p.player2_matrix.map(r => [...r])
  p1Names.value = p.player1_strategies ? [...p.player1_strategies] : p.player1_matrix.map((_, i) => `策略${i+1}`)
  p2Names.value = p.player2_strategies ? [...p.player2_strategies] : p.player1_matrix[0].map((_, j) => `策略${j+1}`)
  result.value = null
}

function getStrategyName(player, idx) {
  if (player === 1) return p1Names.value[idx] || `策略${idx+1}`
  return p2Names.value[idx] || `策略${idx+1}`
}

async function solve() {
  loading.value = true
  try {
    const resp = await axios.post('/api/static-game/solve', {
      player1_matrix: matrix1.value,
      player2_matrix: matrix2.value,
      player1_strategies: p1Names.value,
      player2_strategies: p2Names.value,
    })
    result.value = resp.data
    await nextTick()
    renderBRChart()
  } catch (e) {
    ElMessage.error('求解失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function renderBRChart() {
  if (!brChart.value || !result.value?.best_response_data) return

  const data = result.value.best_response_data

  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(brChart.value)

  if (data.br1_p_given_q && data.br2_q_given_p) {
    // 2x2 game: plot BR curves in (p, q) space
    const br1Series = data.br1_p_given_q.map(d => [d.p, d.q])
    const br2Series = data.br2_q_given_p.map(d => [d.p, d.q])

    const intersections = []
    if (result.value.mixed_nash) {
      intersections.push([
        result.value.mixed_nash.player1_probs[0],
        result.value.mixed_nash.player2_probs[0]
      ])
    }
    for (const eq of result.value.pure_nash) {
      intersections.push([
        eq.player1_strategy === 0 ? 1 : 0,
        eq.player2_strategy === 0 ? 1 : 0
      ])
    }

    chartInstance.setOption({
      title: { text: '最优响应函数 (p = P1选策略1的概率, q = P2选策略1的概率)', textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'item' },
      xAxis: { name: 'p (玩家1)', min: 0, max: 1 },
      yAxis: { name: 'q (玩家2)', min: 0, max: 1 },
      legend: { data: ['BR₁(q)', 'BR₂(p)', '纳什均衡'], bottom: 0 },
      series: [
        {
          name: 'BR₁(q)',
          type: 'line',
          data: br1Series,
          lineStyle: { width: 3, color: '#e74c3c' },
          itemStyle: { color: '#e74c3c' },
          showSymbol: false,
        },
        {
          name: 'BR₂(p)',
          type: 'line',
          data: br2Series,
          lineStyle: { width: 3, color: '#3498db' },
          itemStyle: { color: '#3498db' },
          showSymbol: false,
        },
        {
          name: '纳什均衡',
          type: 'scatter',
          data: intersections,
          symbolSize: 16,
          itemStyle: { color: '#2ecc71', borderColor: '#27ae60', borderWidth: 2 },
        }
      ]
    })
  } else if (data.type === 'general' && data.heatmap) {
    // General matrix: heatmap visualization
    const r = rows.value
    const c = cols.value
    const xLabels = p2Names.value.map((n, i) => n || `策略${i+1}`)
    const yLabels = p1Names.value.map((n, i) => n || `策略${i+1}`)

    // Build heatmap data: value encodes BR status (0=none, 1=BR1, 2=BR2, 3=Nash)
    const heatData = data.heatmap.map(h => {
      let val = 0
      if (h.is_nash) val = 3
      else if (h.is_br1 && h.is_br2) val = 3
      else if (h.is_br1) val = 1
      else if (h.is_br2) val = 2
      return [h.col, h.row, val, h.p1_payoff, h.p2_payoff]
    })

    chartInstance.setOption({
      title: { text: '最优响应矩阵图', subtext: '红=P1最优响应, 蓝=P2最优响应, 绿=纳什均衡', textStyle: { fontSize: 14 } },
      tooltip: {
        formatter: (params) => {
          const d = params.data
          const ri = d[1], ci = d[0]
          const status = d[2] === 3 ? '★ 纳什均衡' : d[2] === 1 ? 'P1最优响应' : d[2] === 2 ? 'P2最优响应' : '—'
          return `(${yLabels[ri]}, ${xLabels[ci]})<br/>收益: (${d[3]}, ${d[4]})<br/>${status}`
        }
      },
      xAxis: { type: 'category', data: xLabels, name: '玩家2', splitArea: { show: true } },
      yAxis: { type: 'category', data: yLabels, name: '玩家1', splitArea: { show: true } },
      visualMap: {
        show: false,
        min: 0, max: 3,
        inRange: {
          color: ['#f5f5f5', '#ffcccc', '#cce5ff', '#c8f7c5']
        }
      },
      series: [{
        type: 'heatmap',
        data: heatData,
        label: {
          show: true,
          formatter: (params) => {
            const d = params.data
            const marker = d[2] === 3 ? '★ ' : ''
            return `${marker}(${d[3]}, ${d[4]})`
          },
          fontSize: 13,
          fontWeight: 'bold',
        },
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
      }]
    })
  }
}

onMounted(async () => {
  try {
    const resp = await axios.get('/api/static-game/presets')
    presets.value = resp.data
  } catch (e) {
    console.error(e)
  }
})
</script>

<style scoped>
.payoff-table {
  border-collapse: collapse;
  width: 100%;
}
.payoff-table th, .payoff-table td {
  border: 1px solid #ebeef5;
  padding: 8px;
  text-align: center;
}
.payoff-table th {
  background: #f5f7fa;
}
</style>
