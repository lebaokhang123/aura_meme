import React, { useState } from 'react';
import { useUI } from '../context/UIContext';

export const ContactPage: React.FC = () => {
  const { user, showToast } = useUI();

  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [bonusChecked, setBonusChecked] = useState(true);
  const isSubmitting = false;
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  const faqs = [
    {
      q: 'Can I contribute to the React codebase?',
      a: 'Absolutely! AuraMeme is our flagship CS302 collaborative project. Visit our GitHub repository or join our Discord developer channel #frontend-dev to pick up issues tagged good-first-issue.',
    },
    {
      q: 'How does Aura get calculated?',
      a: 'Aura values are fixed sample data in this classroom prototype. Rewards and rank progression are planned concepts.',
    },
    {
      q: 'Where can I suggest brand-new meme categories?',
      a: 'Use the contact form on this page with the subject set to "Feature Suggestion", or submit a RFC proposal directly in the #category-polls voice & text lounge on Discord.',
    },
    {
      q: 'How do university research teams collaborate with AuraMeme?',
      a: 'This prototype is a React UI exercise. Research integrations and APIs are not available.',
    },
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !message.trim()) return;

      setIsSubmitted(true);
      showToast('Demo only — your message was not sent or saved.');
      setMessage('');

  };

  const toggleFaq = (index: number) => {
    setActiveFaq(activeFaq === index ? null : index);
  };

  return (
    <div className="w-full">
      <section className="relative w-full overflow-hidden py-8 px-4 lg:px-6">
        {/* Ambient glowing backdrop orbs */}
        <div className="pointer-events-none absolute -top-24 left-1/4 h-96 w-96 rounded-full bg-primary-container/15 blur-[120px]" />
        <div className="pointer-events-none absolute top-1/2 right-10 h-80 w-80 rounded-full bg-secondary-container/15 blur-[100px]" />

        <div className="max-w-7xl mx-auto">
          {/* Breadcrumb & Status Pill Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-6">
            <div className="flex items-center gap-1.5 font-['JetBrains_Mono'] text-xs text-outline">
              <span className="text-on-surface-variant">terminal://</span>
              <span>aurameme</span>
              <span>/</span>
              <span className="text-secondary font-semibold">contact-support</span>
            </div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container-high text-secondary font-['Inter'] text-xs font-semibold shadow-sm">
              <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
              <span>Ticket Desk Active • Average Response &lt; 3h</span>
            </div>
          </div>

          {/* Main Asymmetric Two-Column Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* LEFT COLUMN: Contact Information, Channels & FAQ */}
            <div className="lg:col-span-6 xl:col-span-6 flex flex-col gap-6">
              <div className="flex flex-col gap-2">
                <span className="font-['Inter'] text-xs uppercase tracking-widest text-primary font-bold">
                  Comm Relay • Node CS302
                </span>
                <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-3xl sm:text-4xl text-on-surface tracking-tight">
                  Get in Touch with{' '}
                  <span className="bg-gradient-to-r from-primary via-primary-container to-secondary bg-clip-text text-transparent">
                    AuraMeme
                  </span>
                </h1>
                <p className="font-['Inter'] text-sm sm:text-base text-on-surface-variant max-w-xl leading-relaxed">
                  Have feedback on the React project, found a bug in the Aura leveling system, or want to suggest new meme categories? Drop us a note!
                </p>
              </div>

              {/* Quick Information Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <a
                  className="group flex flex-col justify-between p-3.5 rounded-xl bg-surface-container hover:bg-surface-container-high transition-all shadow-md border border-surface-container-highest/20 cursor-pointer"
                  href="mailto:support@aurameme.dev"
                >
                  <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center text-primary group-hover:scale-105 transition-transform">
                    <span className="material-symbols-outlined text-[20px]">mark_email_unread</span>
                  </div>
                  <div className="pt-3">
                    <span className="font-['Inter'] font-semibold text-[11px] uppercase tracking-wider text-outline block">
                      Project Inquiries
                    </span>
                    <span className="font-['Plus_Jakarta_Sans'] font-semibold text-xs text-on-surface group-hover:text-primary transition-colors block truncate">
                      support@aurameme.dev
                    </span>
                    <span className="font-['Inter'] text-[11px] text-on-surface-variant">Official Dev Mailbox</span>
                  </div>
                </a>

                <a
                  className="group flex flex-col justify-between p-3.5 rounded-xl bg-surface-container hover:bg-surface-container-high transition-all shadow-md border border-surface-container-highest/20 cursor-pointer"
                  href="https://discord.com"
                  target="_blank"
                  rel="noreferrer"
                >
                  <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center text-secondary group-hover:scale-105 transition-transform">
                    <span className="material-symbols-outlined text-[20px]">forum</span>
                  </div>
                  <div className="pt-3">
                    <span className="font-['Inter'] font-semibold text-[11px] uppercase tracking-wider text-outline block">
                      Discord Community
                    </span>
                    <span className="font-['Plus_Jakarta_Sans'] font-semibold text-xs text-on-surface group-hover:text-secondary transition-colors block truncate">
                      discord.gg/aurameme
                    </span>
                    <span className="font-['Inter'] text-[11px] text-secondary font-medium">+4,500 meme creators</span>
                  </div>
                </a>

                <div className="flex flex-col justify-between p-3.5 rounded-xl bg-surface-container shadow-md border border-surface-container-highest/20">
                  <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center text-tertiary">
                    <span className="material-symbols-outlined text-[20px]">school</span>
                  </div>
                  <div className="pt-3">
                    <span className="font-['Inter'] font-semibold text-[11px] uppercase tracking-wider text-outline block">
                      University Dept
                    </span>
                    <span className="font-['Plus_Jakarta_Sans'] font-semibold text-xs text-on-surface block truncate">
                      CS & Software Eng Lab
                    </span>
                    <span className="font-['Inter'] text-[11px] text-on-surface-variant">Hall 4B, Room 218</span>
                  </div>
                </div>
              </div>

              {/* Interactive Micro-Stats / Live Aura Hub Preview */}
              <div className="p-4 sm:p-5 rounded-xl bg-surface-container-low flex flex-col gap-3 shadow-lg border border-surface-container-highest/30">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-[22px]">analytics</span>
                    <span className="font-['Inter'] font-semibold text-xs text-on-surface uppercase tracking-wider">
                      Aura Network Health
                    </span>
                  </div>
                  <span className="font-['JetBrains_Mono'] text-xs px-2 py-0.5 rounded bg-surface-container-highest text-secondary">
                    VITE + REACT RUNNING
                  </span>
                </div>

                {/* Mini HUD stats */}
                <div className="grid grid-cols-3 gap-2 pt-1">
                  <div className="p-2.5 rounded-lg bg-surface-container border border-surface-container-highest/20">
                    <span className="font-['Inter'] text-[11px] text-outline block">Active Creators</span>
                    <span className="font-['Plus_Jakarta_Sans'] font-bold text-base text-on-surface">4,812</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-container border border-surface-container-highest/20">
                    <span className="font-['Inter'] text-[11px] text-outline block">Aura Burn/Day</span>
                    <span className="font-['Plus_Jakarta_Sans'] font-bold text-base text-secondary">182.4k</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-container border border-surface-container-highest/20">
                    <span className="font-['Inter'] text-[11px] text-outline block">PRs Merged</span>
                    <span className="font-['Plus_Jakarta_Sans'] font-bold text-base text-primary">64</span>
                  </div>
                </div>

                {/* XP / Network Bar */}
                <div className="flex flex-col gap-1.5 pt-1">
                  <div className="flex justify-between font-['Inter'] text-xs text-outline">
                    <span>Community Sprint Quota</span>
                    <span className="text-on-surface font-semibold">88% Achieved</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface-container-highest overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-primary via-primary-container to-secondary rounded-full"
                      style={{ width: '88%' }}
                    />
                  </div>
                </div>
              </div>

              {/* FAQ Accordion Block */}
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2 pb-1">
                  <span className="material-symbols-outlined text-secondary text-[20px]">help</span>
                  <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-lg text-on-surface">
                    Frequently Asked Questions
                  </h2>
                </div>

                {faqs.map((faq, idx) => {
                  const isOpen = activeFaq === idx;
                  return (
                    <div
                      key={idx}
                      className="rounded-xl bg-surface-container-low transition-colors duration-200 border border-surface-container-highest/20"
                    >
                      <button
                        className="w-full p-4 flex items-center justify-between text-left cursor-pointer"
                        onClick={() => toggleFaq(idx)}
                        type="button"
                      >
                        <span className="font-['Plus_Jakarta_Sans'] font-semibold text-xs sm:text-sm text-on-surface pr-3">
                          {faq.q}
                        </span>
                        <span
                          className={`material-symbols-outlined text-on-surface-variant transition-transform duration-200 ${
                            isOpen ? 'rotate-180 text-secondary' : ''
                          }`}
                        >
                          expand_more
                        </span>
                      </button>
                      {isOpen && (
                        <div className="px-4 pb-4 pt-0 text-on-surface-variant font-['Inter'] text-xs sm:text-sm leading-relaxed border-t border-surface-container-highest/20 mt-1 pt-3">
                          {faq.a}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* RIGHT COLUMN: Interactive Contact Form Card with Glow */}
            <div className="lg:col-span-6 xl:col-span-6 sticky top-20">
              <div className="relative rounded-2xl bg-surface-container p-6 lg:p-8 shadow-[0_12px_48px_-8px_rgba(160,120,255,0.2)] border border-surface-container-highest/40">
                <div className="pointer-events-none absolute -top-12 -right-12 h-44 w-44 rounded-full bg-primary-container/20 blur-3xl" />

                {/* Card Header */}
                <div className="flex items-center justify-between pb-4">
                  <div className="flex flex-col">
                    <span className="font-['Inter'] text-xs uppercase tracking-wider text-secondary font-bold">
                      Encrypted Dispatch
                    </span>
                    <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-2xl text-on-surface">
                      Send us a Message
                    </h2>
                  </div>
                  <div className="w-11 h-11 rounded-xl bg-surface-container-high flex items-center justify-center text-primary-fixed shadow-sm">
                    <span className="material-symbols-outlined text-[24px]">send</span>
                  </div>
                </div>

                {/* Form */}
                <p className="text-xs text-secondary mb-3">UI demo only. No data is sent or saved.</p>
              <form className="flex flex-col gap-4 mt-2" onSubmit={handleSubmit}>
                  {/* Name & Email Row */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1">
                      <label className="font-['Inter'] font-semibold text-xs text-on-surface">Your Name</label>
                      <div className="relative flex items-center">
                        <span className="material-symbols-outlined absolute left-3 text-outline text-[18px] pointer-events-none">
                          person
                        </span>
                        <input
                          className="w-full h-11 pl-10 pr-3 rounded-xl bg-surface-container-lowest text-on-surface placeholder:text-outline font-['Inter'] text-xs focus:outline-none focus:ring-1 focus:ring-primary transition-all border border-surface-container-highest/30"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          placeholder="e.g. Alex Chen"
                          required
                          type="text"
                        />
                      </div>
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="font-['Inter'] font-semibold text-xs text-on-surface">Email Address</label>
                      <div className="relative flex items-center">
                        <span className="material-symbols-outlined absolute left-3 text-outline text-[18px] pointer-events-none">
                          alternate_email
                        </span>
                        <input
                          className="w-full h-11 pl-10 pr-3 rounded-xl bg-surface-container-lowest text-on-surface placeholder:text-outline font-['Inter'] text-xs focus:outline-none focus:ring-1 focus:ring-primary transition-all border border-surface-container-highest/30"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          placeholder="alex@university.edu"
                          required
                          type="email"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Subject Dropdown */}
                  <div className="flex flex-col gap-1">
                    <label className="font-['Inter'] font-semibold text-xs text-on-surface">Subject Category</label>
                    <div className="relative flex items-center">
                      <span className="material-symbols-outlined absolute left-3 text-outline text-[18px] pointer-events-none">
                        tag
                      </span>
                      <select
                        className="w-full h-11 pl-10 pr-10 rounded-xl bg-surface-container-lowest text-on-surface font-['Inter'] text-xs focus:outline-none focus:ring-1 focus:ring-primary transition-all border border-surface-container-highest/30 appearance-none cursor-pointer"
                        value={subject}
                        onChange={(e) => setSubject(e.target.value)}
                        required
                      >
                        <option className="bg-surface-container" disabled value="">
                          Select inquiry type...
                        </option>
                        <option className="bg-surface-container" value="bug">
                          Bug Report
                        </option>
                        <option className="bg-surface-container" value="feature">
                          Feature Suggestion
                        </option>
                        <option className="bg-surface-container" value="aura">
                          Aura Leveling Question
                        </option>
                        <option className="bg-surface-container" value="other">
                          Other
                        </option>
                      </select>
                      <span className="material-symbols-outlined absolute right-3 text-outline text-[20px] pointer-events-none">
                        unfold_more
                      </span>
                    </div>
                  </div>

                  {/* Message Field */}
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <label className="font-['Inter'] font-semibold text-xs text-on-surface">
                        Message / Meme Proposal
                      </label>
                      <span className="font-['JetBrains_Mono'] text-xs text-outline">
                        {message.length} / 500
                      </span>
                    </div>
                    <textarea
                      className="w-full p-3 rounded-xl bg-surface-container-lowest text-on-surface placeholder:text-outline font-['Inter'] text-xs focus:outline-none focus:ring-1 focus:ring-primary transition-all resize-none border border-surface-container-highest/30"
                      maxLength={500}
                      rows={4}
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      placeholder="Type your message or meme ideas here..."
                      required
                    />
                  </div>

                  {/* Aura Bonus Checkbox */}
                  <div className="p-3 rounded-xl bg-surface-container-low flex items-start gap-3 border border-surface-container-highest/20">
                    <label className="relative flex items-center cursor-pointer mt-0.5">
                      <input
                        checked={bonusChecked}
                        onChange={(e) => setBonusChecked(e.target.checked)}
                        className="peer sr-only"
                        type="checkbox"
                      />
                      <div className="w-5 h-5 rounded bg-surface-container-lowest peer-checked:bg-primary transition-colors flex items-center justify-center border border-surface-container-highest">
                        <span className="material-symbols-outlined text-[16px] text-on-primary scale-0 peer-checked:scale-100 transition-transform">
                          check
                        </span>
                      </div>
                    </label>
                    <div className="flex flex-col">
                      <label
                        className="font-['Inter'] font-semibold text-xs text-on-surface cursor-pointer select-none"
                        onClick={() => setBonusChecked(!bonusChecked)}
                      >
                        Send me a copy and grant <span className="text-secondary font-bold">+25 bonus Aura</span> on my account
                      </label>
                      <span className="font-['Inter'] text-[11px] text-on-surface-variant">
                        Credited instantly to user profile if email matches your authenticated AuraMeme account.
                      </span>
                    </div>
                  </div>

                  {/* Submit Button */}
                  <button
                    disabled={isSubmitting}
                    className="w-full h-12 rounded-xl bg-gradient-to-r from-primary-container via-inverse-primary to-secondary text-on-primary font-['Plus_Jakarta_Sans'] font-bold text-sm flex items-center justify-center gap-2 shadow-[0_0_24px_rgba(160,120,255,0.4)] hover:shadow-[0_0_32px_rgba(76,215,246,0.6)] hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer disabled:opacity-60"
                    type="submit"
                  >
                    {isSubmitting ? (
                      <>
                        <span className="material-symbols-outlined text-[20px] animate-spin">refresh</span>
                        <span>Transmitting...</span>
                      </>
                    ) : (
                      <>
                        <span>Send Message</span>
                        <span className="material-symbols-outlined text-[20px]">send</span>
                      </>
                    )}
                  </button>
                </form>

                {/* Success Notification Card */}
                {isSubmitted && (
                  <div className="mt-4 p-3.5 rounded-xl bg-surface-container-lowest border border-secondary/30 shadow-xl flex items-start gap-3">
                    <div className="w-9 h-9 rounded-full bg-secondary/20 flex items-center justify-center text-secondary shrink-0">
                      <span className="material-symbols-outlined text-[20px]">verified</span>
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-secondary">
                          Demo form completed
                        </span>
                        <span className="px-1.5 py-0.5 rounded-full bg-secondary/15 text-secondary font-['Inter'] text-[10px] font-bold">
                          +25 AURA
                        </span>
                      </div>
                      <p className="font-['Inter'] text-xs text-on-surface-variant">
                        This is a classroom UI preview. Your message was not sent or saved.
                      </p>
                    </div>
                  </div>
                )}

                {/* Footer Guarantee Badge */}
                <div className="pt-4 flex items-center justify-between text-outline font-['Inter'] text-[11px]">
                  <span className="inline-flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px] text-secondary">lock</span>
                    End-to-End SSL Encrypted
                  </span>
                  <span>CS302 Term Project Core</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Community Atmosphere Footer Teaser Banner */}
      <section className="w-full px-4 lg:px-6 pb-8">
        <div className="max-w-7xl mx-auto rounded-2xl bg-surface-container-low p-5 flex flex-col md:flex-row items-center justify-between gap-4 shadow-md border border-surface-container-highest/30">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-surface-container-high flex items-center justify-center text-secondary shrink-0">
              <span className="material-symbols-outlined text-[28px]">electric_bolt</span>
            </div>
            <div className="flex flex-col">
              <span className="font-['Plus_Jakarta_Sans'] font-bold text-base text-on-surface">
                Prefer real-time chat with the devs?
              </span>
              <span className="font-['Inter'] text-xs text-on-surface-variant">
                Join our late-night voice stage or report live bugs on our dedicated Discord channels.
              </span>
            </div>
          </div>
          <a
            className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-surface-container text-on-surface hover:bg-surface-container-high hover:text-secondary font-['Inter'] font-semibold text-xs transition-all shadow-sm shrink-0"
            href="https://discord.com"
            target="_blank"
            rel="noreferrer"
          >
            <span className="material-symbols-outlined text-[18px]">open_in_new</span>
            <span>Open Discord Server</span>
          </a>
        </div>
      </section>
    </div>
  );
};
