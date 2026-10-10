import { createBrowserRouter, Navigate } from "react-router";

import { Layout } from "./Layout";
import { CheckoutPage } from "./pages/CheckoutPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OrderPage } from "./pages/OrderPage";
import { OrdersPage } from "./pages/OrdersPage";
import { PackagePage } from "./pages/PackagePage";
import { SearchPage } from "./pages/SearchPage";

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/search" replace /> },
      { path: "login", element: <LoginPage /> },
      { path: "search", element: <SearchPage /> },
      { path: "package", element: <PackagePage /> },
      { path: "checkout", element: <CheckoutPage /> },
      { path: "orders", element: <OrdersPage /> },
      { path: "orders/:id", element: <OrderPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
