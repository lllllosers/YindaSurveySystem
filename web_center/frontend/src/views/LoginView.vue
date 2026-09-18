<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";

import { useAuthStore } from "../stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const formRef = ref<FormInstance>();
const submitting = ref(false);

const form = reactive({
  username: "",
  password: "",
});

const rules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

async function submit() {
  if (!(await formRef.value?.validate())) return;

  submitting.value = true;
  try {
    await auth.login(form.username, form.password);
    const redirect =
      typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(redirect);
  } catch (error: any) {
    if (error?.response?.status === 429) {
      ElMessage.error("连续登录失败次数过多，请稍后再试");
    } else {
      ElMessage.error("用户名或密码错误");
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-panel">
      <div class="login-brand">
        <div class="brand-mark login-mark">引</div>
        <div>
          <div class="login-title">引大调查数据中心</div>
          <div class="login-subtitle">Yinda Survey Center</div>
        </div>
      </div>

      <div class="login-heading">登录</div>
      <div class="login-description">使用中心端分配的账户进入系统。</div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="submit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" size="large" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="login-button"
          :loading="submitting"
          @click="submit"
        >
          登录
        </el-button>
      </el-form>

      <div class="login-security-note">
        账户会话使用 HttpOnly Cookie；密码仅保存安全哈希。
      </div>
    </div>
  </div>
</template>
