import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { cache } from "./state";
import { App } from "./App";
import "./style.css";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={cache}>
      <BrowserRouter basename="/dashboard">
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
