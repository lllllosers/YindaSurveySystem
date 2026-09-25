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
    <div class="login-visual">
      <div class="login-visual-content">
        <div class="visual-kicker">YINDA SURVEY SYSTEM</div>
        <h1>连接每一次现场调查<br />沉淀可信数据资产</h1>
        <p>面向引大入秦灌区的中央协同与成果管理平台。</p>
        <div class="visual-flow">
          <span>中心安排任务</span><i></i><span>基层离线调查</span><i></i><span>成果集中归档</span>
        </div>
      </div>
      <div class="water-lines" aria-hidden="true"><span></span><span></span><span></span></div>
    </div>

    <div class="login-side">
      <div class="login-panel">
        <div class="login-brand">
          <div class="brand-mark login-mark"><span>引</span></div>
          <div>
            <div class="login-title">引大调查数据中心</div>
            <div class="login-subtitle">YINDA · WEB CENTER</div>
          </div>
        </div>

        <div class="login-heading">欢迎回来</div>
        <div class="login-description">请使用中心端为您分配的账户登录。</div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @keyup.enter="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" size="large" autocomplete="username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              size="large"
              show-password
              autocomplete="current-password"
              placeholder="请输入密码"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-button"
            :loading="submitting"
            @click="submit"
          >
            进入数据中心
          </el-button>
        </el-form>

        <div class="login-security-note"><span></span>登录信息和业务数据均已安全保护</div>
      </div>
      <div class="login-footer">引大入秦灌区现状调查 · V1.2.0</div>
    </div>
  </div>
</template>
