# short-form/ — usually leave this empty

The `long-form/index.tsx` already renders 9:16 by branching on `useVideoConfig()`
(portrait = `height > width`), and short-form rendering falls back to it. Add a
`short-form/index.tsx` here ONLY when a pack needs a genuinely different vertical build
(different layout, not just repositioned). Same import convention as long-form.
