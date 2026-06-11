<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card>
          <template #header><span>拍卖配置</span></template>

          <div style="margin-bottom: 16px;">
            <h4>拍卖类型:</h4>
            <el-radio-group v-model="auctionType" style="display: flex; flex-direction: column; gap: 8px;">
              <el-radio v-for="t in auctionTypes" :key="t.id" :value="t.id">
                <strong>{{ t.name }}</strong>
                <div style="font-size: 11px; color: #909399;">{{ t.description }}</div>
              </el-radio>
            </el-radio-group>
          </div>

          <div style="margin-bottom: 16px;">
            <h4>竞拍者 (私有估值):</h4>
            <div v-for="(bidder, idx) in bidders" :key="idx" style="display: flex; gap: 8px; margin-bottom: 8px; align-items: center;">
              <el-input v-model="bidder.name" size="small" style="width: 80px;" />
              <el-input-number v-model="bidder.valuation" :min="0" :max="1000" size="small" style="width: 120px;" />
              <el-button size="small" type="danger" text @click="removeBidder(idx)" :disabled="bidders.length <= 2">
                删除
              </el-button>
            </div>
            <el-button size="small" @click="addBidder" :disabled="bidders.length >= 8">添加竞拍者</el-button>
          </div>

          <div style="margin-bottom: 16px;">
            <h4>保留价:</h4>
            <el-input-number v-model="reservePrice" :min="0" :max="500" size="small" />
          </div>

          <el-button type="primary" @click="runAuction" :loading="loading" style="width: 100%; margin-bottom: 8px;">
            运行单次拍卖
          </el-button>
          <el-button type="success" @click="compareAuctions" :loading="comparing" style="width: 100%;">
            对比所有机制 ({{ numSims }} 次模拟)
          </el-button>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card v-if="auctionResult">
          <template #header><span>拍卖结果</span></template>

          <el-descriptions :column="2" border>
            <el-descriptions-item label="拍卖类型">{{ getTypeName(auctionResult.auction_type) }}</el-descriptions-item>
            <el-descriptions-item label="赢家">
              <el-tag type="success">{{ auctionResult.winner || '流拍' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="成交价格">{{ auctionResult.price?.toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="赢家估值">{{ auctionResult.winner_valuation?.toFixed(2) }}</el-descriptions-item>
            <el-descriptions-item label="卖家收入">
              <span style="color: #e74c3c; font-weight: bold;">{{ auctionResult.revenue?.toFixed(2) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="买家剩余">
              <span style="color: #2ecc71; font-weight: bold;">{{ auctionResult.surplus?.toFixed(2) }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <!-- Bidding history animation -->
          <div v-if="auctionResult.history" style="margin-top: 20px;">
            <h4>竞价过程:</h4>
            <div style="display: flex; gap: 8px; margin-bottom: 12px;">
              <el-button size="small" @click="startAuctionReplay" :disabled="auctionReplaying">播放</el-button>
              <el-button size="small" @click="stopAuctionReplay">停止</el-button>
            </div>
            <el-timeline>
              <el-timeline-item
                v-for="(h, idx) in visibleHistory"
                :key="idx"
                :type="idx === visibleHistory.length - 1 ? 'success' : 'primary'"
                :timestamp="'价格: ' + h.price?.toFixed(1)"
              >
                {{ h.event }}
              </el-timeline-item>
            </el-timeline>
          </div>

          <!-- Bids table for sealed auctions -->
          <div v-if="auctionResult.bids" style="margin-top: 20px;">
            <h4>出价详情:</h4>
            <el-table :data="auctionResult.bids" size="small" stripe>
              <el-table-column prop="bidder" label="竞拍者" />
              <el-table-column prop="valuation" label="真实估值">
                <template #default="{ row }">{{ row.valuation.toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="bid" label="出价">
                <template #default="{ row }">{{ row.bid.toFixed(2) }}</template>
              </el-table-column>
            </el-table>
          </div>

          <!-- VCG payments -->
          <div v-if="auctionResult.vcg_payments" style="margin-top: 20px;">
            <h4>VCG 支付与效用:</h4>
            <el-table :data="auctionResult.vcg_payments" size="small" stripe>
              <el-table-column prop="bidder" label="竞拍者" />
              <el-table-column prop="payment" label="VCG支付">
                <template #default="{ row }">{{ row.payment.toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="utility" label="效用">
                <template #default="{ row }">{{ row.utility.toFixed(2) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>

        <el-card v-if="comparisonResult" style="margin-top: 20px;">
          <template #header><span>机制对比 ({{ comparisonResult.num_simulations }} 次模拟, {{ Object.keys(comparisonResult.comparison).length }} 种机制)</span></template>
          <div ref="compareChart" style="width: 100%; height: 300px;"></div>
        </el-card>

        <el-card v-if="comparisonResult" style="margin-top: 20px;">
          <template #header><span>收入等价定理验证 — 累计平均收入收敛图</span></template>
          <div ref="convergenceChart" style="width: 100%; height: 350px;"></div>
          <div style="margin-top: 12px; background: #f0f9eb; padding: 12px; border-radius: 4px;">
            <p style="margin: 0; font-size: 13px; color: #555;">
              <strong>观察：</strong>随着模拟次数增加，五种机制的平均卖家收入趋于一致。
              这正是收入等价定理 (Revenue Equivalence Theorem) 的实验验证：
              在独立私有价值 (IPV)、对称竞拍者、风险中性假设下，所有标准拍卖机制产生相同的期望收入。
            </p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'

const auctionTypes = ref([])
const auctionType = ref('english')
const bidders = ref([
  { id: 1, name: '买家A', valuation: 80 },
  { id: 2, name: '买家B', valuation: 60 },
  { id: 3, name: '买家C', valuation: 45 },
  { id: 4, name: '买家D', valuation: 30 },
])
const reservePrice = ref(10)
const numSims = ref(1000)
const loading = ref(false)
const comparing = ref(false)
const auctionResult = ref(null)
const comparisonResult = ref(null)
const compareChart = ref(null)
const convergenceChart = ref(null)
let compareChartInstance = null
let convergenceChartInstance = null

const auctionReplaying = ref(false)
const visibleHistory = ref([])
let auctionReplayTimer = null

const TYPE_NAMES = {
  english: '英式拍卖',
  dutch: '荷兰式拍卖',
  sealed_first: '第一价格密封',
  sealed_second: '第二价格密封',
  vcg: 'VCG机制',
}

function getTypeName(type) {
  return TYPE_NAMES[type] || type
}

function addBidder() {
  const id = bidders.value.length + 1
  bidders.value.push({ id, name: `买家${String.fromCharCode(64 + id)}`, valuation: 50 })
}

function removeBidder(idx) {
  bidders.value.splice(idx, 1)
}

async function runAuction() {
  loading.value = true
  try {
    const resp = await axios.post('/api/auction/simulate', {
      auction_type: auctionType.value,
      bidders: bidders.value,
      reserve_price: reservePrice.value,
    })
    auctionResult.value = resp.data
    visibleHistory.value = resp.data.history || []
    stopAuctionReplay()
  } catch (e) {
    ElMessage.error('拍卖模拟失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function compareAuctions() {
  comparing.value = true
  try {
    const resp = await axios.post('/api/auction/compare', {
      bidders: bidders.value,
      reserve_price: reservePrice.value,
      num_simulations: numSims.value,
    })
    comparisonResult.value = resp.data
    await nextTick()
    renderCompareChart()
    renderConvergenceChart()
  } catch (e) {
    ElMessage.error('对比模拟失败：' + (e.response?.data?.detail || e.message))
  } finally {
    comparing.value = false
  }
}

function renderCompareChart() {
  if (!compareChart.value || !comparisonResult.value) return
  if (compareChartInstance) compareChartInstance.dispose()
  compareChartInstance = echarts.init(compareChart.value)

  const comp = comparisonResult.value.comparison
  const types = Object.keys(comp)
  const names = types.map(t => getTypeName(t))

  compareChartInstance.setOption({
    title: { text: '各机制平均收入与买家剩余对比', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['卖家平均收入', '买家平均剩余'], bottom: 0 },
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value', name: '金额' },
    series: [
      {
        name: '卖家平均收入',
        type: 'bar',
        data: types.map(t => comp[t].avg_revenue.toFixed(2)),
        itemStyle: { color: '#e74c3c' },
        label: { show: true, position: 'top', formatter: '{c}' }
      },
      {
        name: '买家平均剩余',
        type: 'bar',
        data: types.map(t => comp[t].avg_surplus.toFixed(2)),
        itemStyle: { color: '#2ecc71' },
        label: { show: true, position: 'top', formatter: '{c}' }
      }
    ]
  })
}

function renderConvergenceChart() {
  if (!convergenceChart.value || !comparisonResult.value?.convergence) return
  if (convergenceChartInstance) convergenceChartInstance.dispose()
  convergenceChartInstance = echarts.init(convergenceChart.value)

  const conv = comparisonResult.value.convergence
  const colors = { english: '#e74c3c', dutch: '#f39c12', sealed_first: '#9b59b6', sealed_second: '#3498db', vcg: '#2ecc71' }
  const series = Object.keys(conv).map(atype => {
    const data = conv[atype]
    return {
      name: getTypeName(atype),
      type: 'line',
      data: data,
      smooth: true,
      lineStyle: { width: 2, color: colors[atype] },
      itemStyle: { color: colors[atype] },
      showSymbol: false,
    }
  })

  const maxLen = Math.max(...Object.values(conv).map(d => d.length))
  const step = Math.max(1, Math.floor(comparisonResult.value.num_simulations / maxLen))
  const xData = Array.from({ length: maxLen }, (_, i) => (i + 1) * step)

  convergenceChartInstance.setOption({
    title: { text: '累计平均卖家收入随模拟次数的收敛', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    xAxis: { type: 'category', data: xData, name: '模拟次数' },
    yAxis: { type: 'value', name: '平均收入' },
    series,
  })
}

function startAuctionReplay() {
  if (!auctionResult.value?.history) return
  auctionReplaying.value = true
  visibleHistory.value = []
  let idx = 0
  auctionReplayTimer = setInterval(() => {
    if (idx >= auctionResult.value.history.length) {
      stopAuctionReplay()
      return
    }
    visibleHistory.value.push(auctionResult.value.history[idx])
    idx++
  }, 800)
}

function stopAuctionReplay() {
  auctionReplaying.value = false
  if (auctionReplayTimer) {
    clearInterval(auctionReplayTimer)
    auctionReplayTimer = null
  }
}

onMounted(async () => {
  try {
    const resp = await axios.get('/api/auction/types')
    auctionTypes.value = resp.data
  } catch (e) {
    console.error(e)
  }
})

onUnmounted(() => {
  stopAuctionReplay()
})
</script>
