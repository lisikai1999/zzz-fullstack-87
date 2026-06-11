<template>
  <el-container style="min-height: 100vh">
    <el-header style="background: #2c3e50; display: flex; align-items: center; padding: 0 24px;">
      <h1 style="color: white; margin: 0; font-size: 20px;">博弈论仿真平台</h1>
      <el-menu
        :default-active="$route.path"
        mode="horizontal"
        router
        style="margin-left: 40px; background: transparent; border: none;"
        text-color="#ecf0f1"
        active-text-color="#3498db"
      >
        <el-menu-item index="/static-game">静态博弈</el-menu-item>
        <el-menu-item index="/repeated-game">重复博弈</el-menu-item>
        <el-menu-item index="/auction">拍卖机制</el-menu-item>
      </el-menu>
    </el-header>
    <el-main style="padding: 24px; background: #f5f7fa;">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.el-header {
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  z-index: 10;
}
</style>
