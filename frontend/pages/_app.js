import "../styles/globals.css";
import { useEffect } from "react";
import { initSentry, addBreadcrumb } from "../lib/sentry-config";
import AlertMonitor from "../components/AlertMonitor";

export default function App({ Component, pageProps }) {
  useEffect(() => {
    // Initialize error tracking
    initSentry();

    // Track page navigation
    addBreadcrumb("App initialized", "page-lifecycle");
  }, []);

  return (
    <>
      <Component {...pageProps} />
      <AlertMonitor />
    </>
  );
}
