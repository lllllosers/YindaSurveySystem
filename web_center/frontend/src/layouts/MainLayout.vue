<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  DataAnalysis,
  Coin,
  Document,
  Files,
  Management,
  OfficeBuilding,
  Tickets,
  UserFilled,
} from "@element-plus/icons-vue";

import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const roleLabel = computed(() => {
  const labels = {
    admin: "系统管理员",
    manager: "管理人员",
    reviewer: "审核人员",
    viewer: "查询人员",
  } as const;
  return auth.user ? labels[auth.user.role] : "";
});

async function logout() {
  await auth.logout();
  await router.replace("/login");
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="232px" class="sidebar">
      <div class="brand">
        <div class="brand-mark"><span>引</span></div>
        <div>
          <div class="brand-title">引大调查数据中心</div>
          <div class="brand-subtitle">中心业务管理平台</div>
        </div>
      </div>

      <el-menu
        :default-active="route.path"
        router
        class="side-menu"
        background-color="transparent"
        text-color="#c8d1dc"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <el-icon><Management /></el-icon>
          <span>项目与批次</span>
        </el-menu-item>
        <el-menu-item
          v-if="auth.hasPermission('master_data.read')"
          index="/master-data"
        >
          <el-icon><OfficeBuilding /></el-icon>
          <span>基础资料</span>
        </el-menu-item>
        <el-menu-item v-if="auth.hasPermission('tasks.read')" index="/tasks">
          <el-icon><Document /></el-icon>
          <span>调查任务</span>
        </el-menu-item>
        <el-menu-item v-if="auth.hasPermission('results.read')" index="/results">
          <el-icon><Files /></el-icon>
          <span>成果接收与审核</span>
        </el-menu-item>
        <el-menu-item v-if="auth.hasPermission('central_records.read')" index="/central-records">
          <el-icon><Coin /></el-icon>
          <span>正式成果库</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/users">
          <el-icon><UserFilled /></el-icon>
          <span>用户与权限</span>
        </el-menu-item>
        <el-menu-item
          v-if="auth.hasPermission('audit.read')"
          index="/audit"
        >
          <el-icon><Tickets /></el-icon>
          <span>操作记录</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <div class="page-title">引大入秦灌区现状调查数据中心</div>
          <div class="page-subtitle">
            <span class="live-dot"></span>
            中心端 · 与桌面端协同工作
          </div>
        </div>

        <el-dropdown>
          <div class="user-menu">
            <div class="user-avatar">
              {{ auth.user?.display_name?.slice(0, 1) ?? "用" }}
            </div>
            <div class="user-meta">
              <span class="user-name">{{ auth.user?.display_name }}</span>
              <span class="user-role">{{ roleLabel }}</span>
            </div>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{ auth.user?.username }}</el-dropdown-item>
              <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
