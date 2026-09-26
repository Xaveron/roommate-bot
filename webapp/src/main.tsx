import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { webApp } from "./telegram";

const app = webApp();
app?.ready();
app?.expand();
// Scrolling a long list must not close the app (Telegram 7.7+).
if (app?.isVersionAtLeast?.("7.7")) app.disableVerticalSwipes();

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
