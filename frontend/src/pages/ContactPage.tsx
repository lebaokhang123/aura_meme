import { useState } from 'react';
import { Link } from 'react-router-dom';

const faqs = [
  {
    question: 'Can I send a message from this form?',
    answer: 'Not yet. This local preview lets you explore the form without sending or saving your message.',
  },
  {
    question: 'Where can I follow the project?',
    answer:
      'The AuraMeme GitHub repository is linked below. Public contact channels will be added after confirmation.',
  },
  {
    question: 'Does contacting the team grant Aura?',
    answer: 'No. Contact messages do not grant Aura or other community rewards.',
  },
];

export function ContactPage() {
  const [activeFaq, setActiveFaq] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  return (
    <div className="relative w-full isolate">
      <div aria-hidden="true" className="absolute inset-0 overflow-clip pointer-events-none -z-10">
        <div className="absolute -top-24 left-1/4 h-96 w-96 bg-primary-container/15 blur-[120px] rounded-full" />
        <div className="absolute top-1/2 right-10 h-80 w-80 bg-secondary-container/15 blur-[100px] rounded-full" />
      </div>
      <div className="max-w-7xl mx-auto px-4 lg:px-6 py-8">
        <div className="font-mono text-xs text-outline mb-7">
          aurameme / <span className="text-secondary">contact</span>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <section className="lg:col-span-6 min-w-0">
            <span className="text-xs uppercase tracking-widest text-primary font-bold">
              A conversation starts here
            </span>
            <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-3xl sm:text-4xl mt-3">
              Get in Touch with{' '}
              <span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                AuraMeme
              </span>
            </h1>
            <p className="text-sm text-on-surface-variant leading-relaxed mt-4">
              Feedback, a new category, or a meme worth talking about? This is a preview of how you will reach
              the team.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-7">
              <a
                href="https://github.com/lebaokhang123/aura_meme"
                target="_blank"
                rel="noreferrer"
                className="group p-5 rounded-xl bg-surface-container border border-surface-container-highest/20 shadow-md hover:bg-surface-container-high transition-colors"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-primary">
                  code
                </span>
                <h2 className="text-xs uppercase tracking-wider font-semibold mt-4">Project repository</h2>
                <p className="text-xs text-on-surface-variant mt-2">
                  Follow AuraMeme on GitHub<span className="sr-only">(opens in a new tab)</span>
                </p>
              </a>
              <Link
                to="/about#team"
                className="p-5 rounded-xl bg-surface-container border border-surface-container-highest/20 shadow-md hover:bg-surface-container-high transition-colors"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-secondary">
                  groups
                </span>
                <h2 className="text-xs uppercase tracking-wider font-semibold mt-4">Meet the team</h2>
                <p className="text-xs text-on-surface-variant mt-2">Khang & Kiên</p>
              </Link>
            </div>
            <div className="mt-7 rounded-xl bg-surface-container-low border border-surface-container-highest/30 p-5">
              <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-base mb-3">A few quick answers</h2>
              {faqs.map((faq, index) => (
                <div key={faq.question} className="border-t border-surface-container-highest/30">
                  <h3>
                    <button
                      type="button"
                      aria-expanded={activeFaq === index}
                      aria-controls={`faq-${index}`}
                      onClick={() => setActiveFaq(activeFaq === index ? null : index)}
                      className="w-full min-h-12 py-3 text-left text-xs flex justify-between gap-3 items-center"
                    >
                      {faq.question}
                      <span
                        aria-hidden="true"
                        className="material-symbols-outlined text-[18px] text-outline shrink-0"
                      >
                        {activeFaq === index ? 'close' : 'expand_more'}
                      </span>
                    </button>
                  </h3>
                  <p
                    id={`faq-${index}`}
                    hidden={activeFaq !== index}
                    className="text-xs text-on-surface-variant leading-relaxed pb-4"
                  >
                    {faq.answer}
                  </p>
                </div>
              ))}
            </div>
          </section>
          <section className="lg:col-span-6 min-w-0 bg-surface-container-low/95 rounded-xl p-6 sm:p-8 border border-surface-container-highest/30 shadow-2xl">
            <span className="text-[10px] uppercase tracking-widest text-primary font-semibold">
              Contact form preview
            </span>
            <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-2xl mt-2">Send us a Message</h2>
            <p id="contact-preview" className="text-xs text-on-surface-variant leading-relaxed mt-3 mb-6">
              Messages are not connected yet. Please use sample details here; nothing is sent or saved.
            </p>
            <form
              aria-describedby="contact-preview"
              className="flex flex-col gap-5"
              onSubmit={(event) => {
                event.preventDefault();
                setMessage('Contact is not connected yet. Your message was not sent or saved.');
              }}
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="contact-name" className="text-xs font-semibold block mb-2">
                    Your name
                  </label>
                  <input
                    id="contact-name"
                    name="name"
                    autoComplete="name"
                    required
                    placeholder="Your name"
                    className="w-full min-w-0 bg-surface-container-lowest border border-surface-container-highest/50 rounded-lg px-3 py-3 text-sm placeholder:text-outline"
                  />
                </div>
                <div>
                  <label htmlFor="contact-email" className="text-xs font-semibold block mb-2">
                    Email address
                  </label>
                  <input
                    id="contact-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    placeholder="you@example.com"
                    className="w-full min-w-0 bg-surface-container-lowest border border-surface-container-highest/50 rounded-lg px-3 py-3 text-sm placeholder:text-outline"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="contact-subject" className="text-xs font-semibold block mb-2">
                  Subject
                </label>
                <select
                  id="contact-subject"
                  name="subject"
                  required
                  defaultValue=""
                  className="w-full min-w-0 bg-surface-container-lowest border border-surface-container-highest/50 rounded-lg px-3 py-3 text-sm"
                >
                  <option value="" disabled>
                    Select a subject...
                  </option>
                  <option value="feedback">Feedback</option>
                  <option value="category">Category suggestion</option>
                  <option value="issue">Report an issue</option>
                </select>
              </div>
              <div>
                <label htmlFor="contact-message" className="text-xs font-semibold block mb-2">
                  Message
                </label>
                <textarea
                  id="contact-message"
                  name="message"
                  rows={6}
                  required
                  placeholder="What's on your mind?"
                  className="w-full min-w-0 resize-y bg-surface-container-lowest border border-surface-container-highest/50 rounded-lg px-3 py-3 text-sm placeholder:text-outline"
                />
              </div>
              <button
                type="submit"
                className="min-h-12 rounded-xl bg-gradient-to-r from-primary-container via-primary-fixed-dim to-secondary text-on-primary-fixed font-['Plus_Jakarta_Sans'] font-bold text-sm shadow-lg transition-shadow hover:shadow-primary/25 inline-flex items-center justify-center gap-2"
              >
                Preview message
                <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
                  send
                </span>
              </button>
            </form>
            {message && (
              <p
                role="status"
                className="mt-4 bg-secondary/10 border border-secondary/20 rounded-lg p-3 text-xs text-secondary leading-relaxed"
              >
                {message}
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
