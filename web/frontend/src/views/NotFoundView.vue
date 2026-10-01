<script setup lang="ts">
import { ArrowLeft, HomeFilled } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="friendly-missing-page">
    <div class="missing-mark">引</div>
    <div class="eyebrow">页面暂不可用</div>
    <h1>没有找到您要打开的业务页面</h1>
    <p>页面地址可能已更新，也可能是服务正在切换版本。您可以返回工作台后重新进入对应功能。</p>
    <div class="missing-actions">
      <el-button :icon="ArrowLeft" @click="router.back()">返回上一页</el-button>
      <el-button type="primary" :icon="HomeFilled" @click="router.push('/')">回到工作台</el-button>
    </div>
  </div>
</template>
