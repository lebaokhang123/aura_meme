// AUTO-PORT from Stitch: stitch_aurameme_login_signup/ng_k_aurameme_hi_u_ng_meme_trail_fx_323/code.html.
// Upgraded with Lucian UX/UI #244 Register Validation & #401 Google Sign-In.
import React from 'react';
import LucianRegisterForm from '../components/LucianRegisterForm.jsx';

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
            { className: "w-full grid grid-cols-1 lg:grid-cols-12 gap-space-lg lg:gap-0 bg-surface-container-low rounded-xl shadow-[0_24px_64px_rgba(0,0,0,0.6)] overflow-hidden auth-card" },
            React.createElement(
              "div",
              { className: "lg:col-span-6 relative flex flex-col justify-between p-space-xl overflow-hidden bg-surface-container-lowest select-none cursor-crosshair min-h-[440px] lg:min-h-[620px]", id: "trailStage" },
              React.createElement("div", {
                className: "absolute inset-0 opacity-20 pointer-events-none",
                style: {
                  backgroundImage: "radial-gradient(#d0bcff 0.75px, transparent 0.75px), linear-gradient(to right, rgba(208, 188, 255, 0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(76, 215, 246, 0.04) 1px, transparent 1px)",
                  backgroundSize: "32px 32px, 32px 32px, 32px 32px"
                }
              }),
              React.createElement("div", { className: "absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] h-[340px] bg-secondary-container/30 rounded-full blur-[90px] pointer-events-none" }),
              React.createElement("div", { className: "absolute inset-0 overflow-hidden pointer-events-none z-15", id: "trailContainer" }),
              React.createElement(
                "div",
                { className: "relative z-20 my-auto py-space-lg flex flex-col items-center text-center pointer-events-none" },
                React.createElement(
                  "div",
                  { className: "relative w-56 h-56 sm:w-72 sm:h-72 flex items-center justify-center" },
                  React.createElement("div", { className: "absolute inset-0 rounded-full bg-gradient-to-tr from-secondary-container via-transparent to-tertiary-container opacity-40 blur-2xl animate-pulse pointer-events-none" }),
                  React.createElement(
                    "div",
                    { className: "relative z-10 w-40 h-40 sm:w-52 sm:h-52 flex items-center justify-center transition-transform duration-300 transform-gpu group-hover:scale-105" },
                    React.createElement("img", {
                      alt: "AuraMeme Logo",
                      className: "w-full h-full object-contain drop-shadow-[0_0_36px_rgba(76,215,246,0.6)]",
                      src: "https://lh3.googleusercontent.com/aida-public/AB6AXuAwzShyvfD_cI2xD7ghLw6FF4wlz_qa4DxF28KI-p4duWn9G7z7oheyBgYnKIuMPgCX0jBKCOjIDpgnTS7QAwFf-53qqqleRjAh_GnfZODnvACUv1AK4so2klTkp1Te2_HOmQrZqdxlxLSgKnHKhEN7gWLHBpt1GHnyMha45bCW043OVFHhtONAKArXZNuQMaqJrCRVkpk9rQgIOJx12ySaOTA9k6XbLZHVOxsE5eFc916SKk5gA4zt"
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
                    "Tạo tài khoản AuraMeme"
                  )
                ),
                React.createElement(LucianRegisterForm, null)
              )
            )
          )
        )
      ),
      React.createElement("span", { "data-stitch-script-slot": "0", style: { display: "none" } })
    )
  );
}
