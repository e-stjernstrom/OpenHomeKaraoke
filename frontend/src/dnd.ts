import type { Modifier } from '@dnd-kit/core';

/** Only move rows up and down (the same as @dnd-kit/modifiers, without one more package). */
export const restrictToVerticalAxis: Modifier = ({ transform }) => ({ ...transform, x: 0 });
