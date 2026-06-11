import { createRouter, createWebHistory } from 'vue-router'
import StaticGame from '../views/StaticGame.vue'
import RepeatedGame from '../views/RepeatedGame.vue'
import Auction from '../views/Auction.vue'

const routes = [
  { path: '/', redirect: '/static-game' },
  { path: '/static-game', component: StaticGame },
  { path: '/repeated-game', component: RepeatedGame },
  { path: '/auction', component: Auction },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
