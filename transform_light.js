const fs = require('fs');

let css = fs.readFileSync('frontend/src/index.css', 'utf-8');

// Replace CSS variables in :root
const rootReplacements = {
  '--surface: #0b1325;': '--surface: #f8f9fa;',
  '--surface-dim: #0b1325;': '--surface-dim: #f1f3f5;',
  '--surface-bright: #31394d;': '--surface-bright: #ffffff;',
  '--surface-container-lowest: #060e1f;': '--surface-container-lowest: #ffffff;',
  '--surface-container-low: #131b2e;': '--surface-container-low: #f8f9fa;',
  '--surface-container: #181f32;': '--surface-container: #f1f3f5;',
  '--surface-container-high: #222a3d;': '--surface-container-high: #e9ecef;',
  '--surface-container-highest: #2d3448;': '--surface-container-highest: #dee2e6;',
  '--surface-variant: #2d3448;': '--surface-variant: #e9ecef;',
  
  '--on-surface: #dbe2fb;': '--on-surface: #212529;',
  '--on-surface-variant: #c2c6d6;': '--on-surface-variant: #495057;',
  '--on-background: #dbe2fb;': '--on-background: #212529;',
  '--outline: #8c909f;': '--outline: #ced4da;',
  '--outline-variant: #424754;': '--outline-variant: #adb5bd;',

  '--primary: #adc6ff;': '--primary: #0d6efd;',
  '--primary-dim: #4d8eff;': '--primary-dim: #0b5ed7;',
  '--primary-hover: #9ab8ff;': '--primary-hover: #0a58ca;',
  '--primary-container: #4d8eff;': '--primary-container: #cfe2ff;',
  '--on-primary: #002e6a;': '--on-primary: #ffffff;',
  '--on-primary-container: #00285d;': '--on-primary-container: #084298;',

  '--secondary: #4edea3;': '--secondary: #198754;',
  '--secondary-container: #00a572;': '--secondary-container: #d1e7dd;',
  '--on-secondary: #003824;': '--on-secondary: #ffffff;',
  '--on-secondary-container: #00311f;': '--on-secondary-container: #0f5132;',

  '--tertiary: #f59e42;': '--tertiary: #fd7e14;',
  '--tertiary-container: #865400;': '--tertiary-container: #ffe5d0;',
  '--on-tertiary-container: #4a2c00;': '--on-tertiary-container: #9a4805;',

  '--error: #ffb4ab;': '--error: #dc3545;',
  '--error-container: #93000a;': '--error-container: #f8d7da;',
  '--on-error-container: #ffdad6;': '--on-error-container: #842029;',

  '--inverse-surface: #dbe2fb;': '--inverse-surface: #212529;',
  '--inverse-on-surface: #283043;': '--inverse-on-surface: #f8f9fa;',

  '--green: #4edea3;': '--green: #198754;',
  '--green-bg: rgba(78, 222, 163, 0.12);': '--green-bg: rgba(25, 135, 84, 0.12);',
  '--yellow: #f59e42;': '--yellow: #fd7e14;',
  '--yellow-bg: rgba(245, 158, 66, 0.12);': '--yellow-bg: rgba(253, 126, 20, 0.12);',
  '--red: #ffb4ab;': '--red: #dc3545;',
  '--red-bg: rgba(255, 180, 171, 0.12);': '--red-bg: rgba(220, 53, 69, 0.12);',
  '--accent: #adc6ff;': '--accent: #0d6efd;',
  '--accent-hover: #4d8eff;': '--accent-hover: #0b5ed7;',
  '--accent-glow: rgba(173, 198, 255, 0.1);': '--accent-glow: rgba(13, 110, 253, 0.1);'
};

for (const [key, val] of Object.entries(rootReplacements)) {
  css = css.replace(key, val);
}

// Additional hardcoded values
css = css.replace(/background: rgba\(173, 198, 255, 0\.3\);/g, 'background: rgba(13, 110, 253, 0.3);');
css = css.replace(/color: #dbe2fb;/g, 'color: var(--on-surface);');
css = css.replace(/rgba\(11, 19, 37, 0\.6\)/g, 'rgba(255, 255, 255, 0.8)');
css = css.replace(/rgba\(11, 19, 37, 0\.8\)/g, 'rgba(255, 255, 255, 0.9)');

// Replace gradients in buttons
css = css.replace(/linear-gradient\(135deg,\s*#adc6ff,\s*#4d8eff\)/g, 'linear-gradient(135deg, var(--primary), var(--primary-dim))');
css = css.replace(/color: #00285d;/g, 'color: var(--on-primary);');

// Replace auth-brand-gradient
css = css.replace(/linear-gradient\(135deg, #131b2e, #0b1325\)/g, 'linear-gradient(135deg, var(--primary-container), #ffffff)');
css = css.replace(/color: #fff;/g, 'color: var(--on-surface);');
css = css.replace(/rgba\(255, 255, 255, 0\.1\)/g, 'rgba(0, 0, 0, 0.05)');
css = css.replace(/rgba\(255, 255, 255, 0\.8\)/g, 'var(--primary)');
css = css.replace(/rgba\(255, 255, 255, 0\.7\)/g, 'var(--on-surface-variant)');
css = css.replace(/rgba\(255, 255, 255, 0\.4\)/g, 'var(--on-surface-variant)');
css = css.replace(/rgba\(255, 255, 255, 0\.05\)/g, 'rgba(0, 0, 0, 0.03)');
css = css.replace(/rgba\(255, 255, 255, 0\.3\)/g, 'rgba(0, 0, 0, 0.2)');

// Button backgrounds
css = css.replace(/background: rgba\(255, 255, 255, 0\.05\);/g, 'background: rgba(0, 0, 0, 0.05);');

// Auth page elements specific
css = css.replace(/background: #131b2e;/g, 'background: var(--surface-container);');
css = css.replace(/background: #0b1325;/g, 'background: var(--surface);');
css = css.replace(/color: #adc6ff;/g, 'color: var(--primary);');

fs.writeFileSync('frontend/src/index.css', css);
console.log("Successfully transformed index.css to light mode!");
