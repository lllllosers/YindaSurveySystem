import { createRouter, createWebHistory } from "vue-router";

import MainLayout from "../layouts/MainLayout.vue";
import DashboardView from "../views/DashboardView.vue";
import LoginView from "../views/LoginView.vue";
import ProjectsView from "../views/ProjectsView.vue";
import UsersView from "../views/UsersView.vue";
import AuditView from "../views/AuditView.vue";
import ResultsView from "../views/ResultsView.vue";
import ResultDetailView from "../views/ResultDetailView.vue";
import { useAuthStore } from "../stores/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { public: true },
    },
    {
      path: "/",
      component: MainLayout,
      children: [
        { path: "", name: "dashboard", component: DashboardView },
        { path: "projects", name: "projects", component: ProjectsView },
        {
          path: "results",
          name: "results",
          component: ResultsView,
          meta: { permission: "results.read" },
        },
        {
          path: "results/:submissionUid",
          name: "result-detail",
          component: ResultDetailView,
          meta: { permission: "results.read" },
        },
        {
          path: "users",
          name: "users",
          component: UsersView,
          meta: { adminOnly: true },
        },
        {
          path: "audit",
          name: "audit",
          component: AuditView,
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
