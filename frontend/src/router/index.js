import { createRouter, createWebHistory } from 'vue-router';
import Dashboard from '../views/Dashboard.vue';
import Detail from '../views/Detail.vue';
import StockManager from '../views/StockManager.vue';
import UserConfig from '../views/UserConfig.vue';
import UserLogin from '../views/UserLogin.vue';
import AdminLogin from '../views/AdminLogin.vue';

const routes = [
  { path: '/login', component: UserLogin, meta: { noAuth: true } },
  { path: '/admin/login', component: AdminLogin, meta: { noAuth: true } },
  { path: '/', component: Dashboard },
  { path: '/stocks', component: StockManager },
  { path: '/config', component: UserConfig },
  { path: '/stock/:ticker', component: Detail, props: true },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Route guard
router.beforeEach((to, from, next) => {
  const role = localStorage.getItem('role');
  const userId = localStorage.getItem('user_id');
  const adminId = localStorage.getItem('admin_id');

  if (to.meta.noAuth) {
    next();
  } else {
    if (!role || (!userId && !adminId)) {
      next('/login');
    } else {
      next();
    }
  }
});

export default router;