import "../styles/globals.css";
import { useEffect } from "react";
import { initSentry, addBreadcrumb } from "../lib/sentry-config";

export default function App({ Component, pageProps }) {
  useEffect(() => {
    // Initialize error tracking
    initSentry();

    // Track page navigation
    addBreadcrumb("App initialized", "page-lifecycle");
  }, []);

  return <Component {...pageProps} />;
}
