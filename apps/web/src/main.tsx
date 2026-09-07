import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { supportsCrossFade } from "./screen-change";
import "./styles.css";

/* Marks the document when the browser can cross-fade a screen change itself, so the
   fallback keyframes in styles.css stand down rather than playing on top of it. */
if (supportsCrossFade()) document.documentElement.classList.add("can-cross-fade");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
