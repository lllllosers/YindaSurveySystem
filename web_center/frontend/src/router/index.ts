import { createRouter, createWebHistory } from "vue-router";

import MainLayout from "../layouts/MainLayout.vue";
import { useAuthStore } from "../stores/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("../views/LoginView.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      component: MainLayout,
      children: [
        {
          path: "",
          name: "dashboard",
          component: () => import("../views/DashboardView.vue"),
        },
        {
          path: "projects",
          name: "projects",
          component: () => import("../views/ProjectsView.vue"),
        },
        {
          path: "master-data",
          name: "master-data",
          component: () => import("../views/MasterDataView.vue"),
          meta: { permission: "master_data.read" },
        },
        {
          path: "tasks",
          name: "tasks",
          component: () => import("../views/TasksView.vue"),
          meta: { permission: "tasks.read" },
        },
        {
          path: "results",
          name: "results",
          component: () => import("../views/ResultsView.vue"),
          meta: { permission: "results.read" },
        },
        {
          path: "results/:submissionUid",
          name: "result-detail",
          component: () => import("../views/ResultDetailView.vue"),
          meta: { permission: "results.read" },
        },
        {
          path: "users",
          name: "users",
          component: () => import("../views/UsersView.vue"),
          meta: { adminOnly: true },
        },
        {
          path: "audit",
          name: "audit",
          component: () => import("../views/AuditView.vue"),
          meta: { permission: "audit.read" },
        },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  if (!auth.initialized) {
    await auth.bootstrap();
  }

  if (to.meta.public) {
    if (to.name === "login" && auth.isAuthenticated) {
      return { name: "dashboard" };
    }
    return true;
  }

  if (!auth.isAuthenticated) {
    return {
      name: "login",
      query: { redirect: to.fullPath },
    };
  }

  if (to.meta.adminOnly && !auth.isAdmin) {
    return { name: "dashboard" };
  }

  if (
    typeof to.meta.permission === "string" &&
    !auth.hasPermission(to.meta.permission)
  ) {
    return { name: "dashboard" };
  }

  return true;
});
