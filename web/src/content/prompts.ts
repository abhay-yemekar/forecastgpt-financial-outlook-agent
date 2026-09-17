/** Curated Ask-box presets, grouped by category. Users click to fill. */
export interface PromptGroup {
  category: string
  icon: string
  prompts: string[]
}

export const PROMPT_GROUPS: PromptGroup[] = [
  {
    category: 'Overview',
    icon: '◈',
    prompts: [
      'Analyze the latest quarterly results and give a qualitative outlook for the next quarter.',
      'Summarize this quarter in plain English: what happened, why, and what it means.',
      'Give me the bull case and the bear case for the next two quarters.',
      'What changed since the previous quarter, and how material is each change?',
    ],
  },
  {
    category: 'Margins & costs',
    icon: '∑',
    prompts: [
      'Analyze operating-margin trajectory: which cost lines drove the change and is it sustainable?',
      'How are employee costs and utilisation trending? What does it imply for next-quarter margins?',
      'Which currency or pricing headwinds/tailwinds should I expect on margins next quarter?',
      'Compare revenue growth vs profit growth — what is the operating leverage story?',
    ],
  },
  {
    category: 'Risks',
    icon: '⚠',
    prompts: [
      'What are the top risks management flagged, ranked by likely impact next quarter?',
      'Any early-warning signs in this quarter (client concentration, attrition, receivables, guidance cuts)?',
      'What could make next quarter miss consensus expectations?',
      'How exposed is the company to a demand slowdown in its major markets?',
    ],
  },
  {
    category: 'Guidance & outlook',
    icon: '⧗',
    prompts: [
      'What forward-looking statements did management make, and how confident do they sound?',
      'Interpret the demand pipeline commentary: is growth accelerating or decelerating?',
      'Based on this quarter’s momentum, project revenue and margin direction for the next quarter.',
      'What are the key monitorables I should track before the next results?',
    ],
  },
  {
    category: 'Management commentary',
    icon: '❖',
    prompts: [
      'What did management emphasize most on the earnings call, in their own words?',
      'How consistent is management’s tone this quarter versus last quarter?',
      'Summarize CFO commentary on cash flow, capital allocation and buybacks/dividends.',
      'Which analyst questions made management uncomfortable, and what does that signal?',
    ],
  },
  {
    category: 'Strategy & moat',
    icon: '⚙',
    prompts: [
      'How is the company positioning itself in AI/GenAI — hype or real revenue?',
      'What is the competitive moat story this quarter: wins, losses, market-share evidence?',
      'Summarize capex and investment commentary — what are they betting on?',
      'Which segments/products are the growth engines, and which are dragging?',
    ],
  },
]
