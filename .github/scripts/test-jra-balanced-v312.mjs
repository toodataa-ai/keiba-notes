// JRA v3.12 prereace CI compatibility: preserve original bounded-risk B-choice
// assertions, then check exact quote gates and union-hit audit overlay.
import './test-jra-balanced-v311.mjs';
import './test-jra-purchase-audit-v312.mjs';
import './test-jra-prestart-pipeline-v312.mjs';
console.log('PASS v3.12 inherited risk cap, profit floor, candidate-price completeness and set audit');
