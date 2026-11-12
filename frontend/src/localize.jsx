import React from 'react';
import { usePreferences } from './PreferencesContext.jsx';
import { hasTranslation, translate } from './preferences.js';
import { SwapText } from './components/SwapText.jsx';
import posts from './feed-posts.json' with { type: 'json' };
const userCopy = new Set(posts.flatMap(post => [post.content, post.title]).filter(Boolean));

function localize(node, language, animate = true) {
  if (typeof node === 'string') {
    if (!hasTranslation(node)) return node;
    if (!animate) return translate(node, language);
    const core = node.trim(), at = node.indexOf(core);
    return <React.Fragment>{node.slice(0, at)}<SwapText source={core} />{node.slice(at + core.length)}</React.Fragment>;
  }
  if (Array.isArray(node)) return node.map((child, index) => {
    const result = localize(child, language, animate);
    return React.isValidElement(result) ? React.cloneElement(result, { key: child?.key ?? index }) : result;
  });
  if (!React.isValidElement(node) || typeof node.type !== 'string' && node.type !== React.Fragment) return node;
  const props = { ...node.props };
  if (React.Children.toArray(props.children).some(child => typeof child === 'string' && userCopy.has(child.trim()))) props.lang = 'vi';
  for (const key of ['aria-label', 'title', 'alt', 'placeholder']) if (typeof props[key] === 'string') props[key] = translate(props[key], language);
  if (props.className?.includes('material-symbols')) return React.cloneElement(node, { ...props, 'aria-hidden': true });
  if (props.translate === 'no') return React.cloneElement(node, props);
  // Keep mixed-color headings in one text flow so mobile line breaks match Stitch.
  if (node.type === 'h1' && animate) return React.cloneElement(node, props, <SwapText block renderText={shown => localize(props.children, shown, false)} />);
  const noSpan = ['option', 'textarea', 'script', 'style'].includes(node.type);
  return React.cloneElement(node, props, localize(props.children, language, animate && !noSpan));
}
// Each source component keeps its own hooks, props and handlers; only its returned text is adapted.
export function useLocalized() {
  const { language } = usePreferences();
  return tree => localize(tree, language);
}
export function LocalizedPage({ component: Component }) {
  const render = useLocalized();
  return render(Component());
}
