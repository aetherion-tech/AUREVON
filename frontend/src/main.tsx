import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { cache } from "./state";
import { App } from "./App";
import "./style.css";
const router = createBrowserRouter([{ path: "*", element: <App /> }], {
  basename: "/dashboard",
});
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={cache}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
