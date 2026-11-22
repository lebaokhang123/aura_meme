// AUTO-PORT from Stitch: stitch_aurameme_login_signup/ng_nh_p_done/code.html.
// Upgraded with Lucian UX/UI #403 Email Sign-In Form (Task 7 Polish).
import React from 'react';
import LucianLoginForm from '../components/LucianLoginForm.jsx';

export default function Screen() {
  return React.createElement(
    React.Fragment,
    null,
    React.createElement(
      "main",
      { className: "w-full pt-16 flex-1 flex flex-col bg-transparent auth-page" },
      React.createElement(
        "div",
        { className: "flex flex-col w-full" },
        React.createElement(
          "div",
          { className: "fixed inset-0 pointer-events-none -z-10 overflow-hidden" },
          React.createElement("div", { className: "pointer-events-none absolute -top-10 left-1/4 w-[540px] h-[340px] bg-secondary-container/20 rounded-full blur-[140px] -z-10" }),
          React.createElement("div", { className: "pointer-events-none absolute top-40 right-10 w-[420px] h-[300px] bg-tertiary-container/15 rounded-full blur-[120px] -z-10" }),
          React.createElement("div", {
            className: "absolute inset-0 opacity-40 pointer-events-none -z-10",
            style: {
              backgroundImage: "linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px)",
              backgroundSize: "40px 40px"
            }
          })
        ),
        React.createElement(
          "div",
          { className: "relative w-full max-w-[1360px] mx-auto px-gutter py-space-xl flex items-center justify-center min-h-[calc(100vh-64px)] auth-layout" },
          React.createElement("div", { className: "absolute -top-16 left-1/4 w-[480px] h-[480px] bg-secondary-container/20 rounded-full blur-[140px] pointer-events-none -z-10" }),
          React.createElement("div", { className: "absolute bottom-4 right-1/4 w-[420px] h-[420px] bg-tertiary-container/15 rounded-full blur-[160px] pointer-events-none -z-10" }),
          React.createElement(
            "div",
            { className: "w-full grid grid-cols-1 lg:grid-cols-12 gap-space-lg lg:gap-0 bg-surface-container-low rounded-xl shadow-[0_24px_64px_rgba(0,0,0,0.6)] overflow-hidden border border-outline-variant/30 auth-card" },
            React.createElement(
              "div",
              { className: "lg:col-span-6 relative flex flex-col justify-between p-space-lg sm:p-space-xl overflow-hidden bg-surface-container-lowest select-none cursor-crosshair group min-h-[460px] lg:min-h-[620px]", id: "photoTrailStage" },
              React.createElement("div", {
                className: "absolute inset-0 opacity-25 pointer-events-none",
                style: {
                  backgroundImage: "radial-gradient(#d0bcff 0.75px, transparent 0.75px), linear-gradient(to right, rgba(208, 188, 255, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(76, 215, 246, 0.05) 1px, transparent 1px)",
                  backgroundSize: "32px 32px, 32px 32px, 32px 32px"
                }
              }),
              React.createElement("div", { className: "absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] h-[340px] bg-secondary-container/25 rounded-full blur-[100px] pointer-events-none" }),
              React.createElement("div", { className: "absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[220px] h-[220px] bg-tertiary-container/20 rounded-full blur-[70px] pointer-events-none" }),
              React.createElement("div", { className: "absolute inset-0 overflow-hidden pointer-events-none z-20", id: "photoTrailContainer" }),
              React.createElement(
                "div",
                { className: "relative z-10 my-auto py-space-md flex flex-col items-center text-center pointer-events-none" },
                React.createElement(
                  "div",
                  { className: "relative w-48 h-48 sm:w-60 sm:h-60 flex items-center justify-center" },
                  React.createElement("div", { className: "absolute inset-0 rounded-full bg-gradient-to-tr from-secondary-container via-transparent to-tertiary-container opacity-40 blur-2xl animate-pulse pointer-events-none" }),
                  React.createElement(
                    "div",
                    { className: "relative z-10 w-48 h-48 sm:w-56 sm:h-56 flex items-center justify-center" },
                    React.createElement("img", {
                      alt: "AuraMeme Logo",
                      className: "w-full h-full object-contain drop-shadow-[0_0_36px_rgba(76,215,246,0.65)]",
                      src: "/assets/brand/symbol-dark-2048.png"
                    })
                  )
                )
              )
            ),
            React.createElement(
              "div",
              { className: "lg:col-span-6 bg-surface-container p-space-lg sm:p-space-xl flex flex-col justify-center" },
              React.createElement(
                "div",
                { className: "max-w-md w-full mx-auto" },
                React.createElement(
                  "div",
                  { className: "mb-space-lg" },
                  React.createElement(
                    "h1",
                    { className: "font-headline-lg text-headline-lg text-on-surface font-extrabold tracking-tight text-center" },
                    "Đăng nhập vào AuraMeme"
                  )
                ),
                React.createElement(LucianLoginForm, null)
              )
            )
          )
        )
      ),
      React.createElement("span", { "data-stitch-script-slot": "0", style: { display: "none" } })
    )
  );
}
