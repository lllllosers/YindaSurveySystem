import { createRouter, createWebHistory } from "vue-router";

import MainLayout from "../layouts/MainLayout.vue";
import DashboardView from "../views/DashboardView.vue";
import ProjectsView from "../views/ProjectsView.vue";


export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: MainLayout,
      children: [
        {
          path: "",
          name: "dashboard",
          component: DashboardView,
        },
        {
          path: "projects",
          name: "projects",
          component: ProjectsView,
        },
      ],
    },
  ],
});
