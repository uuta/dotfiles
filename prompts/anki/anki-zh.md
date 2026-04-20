# Anki Chinese Learning Assistant

## Overview
This command helps you learn Chinese by generating comprehensive explanations and Anki flashcard content for Chinese words, phrases, and sentences. It supports both simplified and traditional characters, with simplified as the default. It also supports translation from Japanese to Chinese.

## Usage
```
/anki-zh [word/phrase/sentence] [--traditional]
```

Examples:
- `/anki-zh 学习` - Explains the Chinese word "学习" (simplified)
- `/anki-zh 學習 --traditional` - Explains the Chinese word "學習" (traditional)
- `/anki-zh 我很喜欢学中文` - Explains the Chinese sentence
- `/anki-zh 了解しました` - Provides Chinese translations for the Japanese phrase

## Behavior

### For Chinese Words (e.g., "学习", "預覽")

When you input a Chinese word, I will provide:

1. **Meaning** - Definition in Japanese followed by English translation
2. **Audio File** - Generated pronunciation link (Mandarin)
3. **Pinyin** - Romanization with tone marks (e.g., xuéxí)
4. **Stroke Order** - Character stroke count and writing tips
5. **Part of Speech** - Grammatical category in Japanese
6. **Use Cases** - Common contexts where the word is used (in Japanese)
7. **Character Analysis** - Individual character meanings and radicals (in Japanese)
8. **Trivia** - Interesting facts about the word, etymology (in Japanese with English translation)
9. **Synonyms** - Similar words with explanations of differences (in Japanese)
10. **Standard Examples** - 3 example sentences with Japanese translations (displayed as a list)
11. **Colloquial Examples** - 3 informal usage examples with translations (displayed as a list)
12. **Alternative Forms** - Show both simplified and traditional if different

**Console Display**: All example sentences will be shown in the terminal for easy review before adding to Anki.

**Final Response Format**: After adding to Anki, display a clear summary with:
- Success confirmation
- All standard example sentences
- All colloquial examples  
- Quick pronunciation note (pinyin)

### For Chinese Sentences (e.g., "我很喜欢学中文")

When you input a Chinese sentence, I will provide:

1. **Meaning** - Explanation in Japanese followed by English translation
2. **Audio File** - Generated pronunciation link (Mandarin)
3. **Pinyin** - Full sentence romanization with tone marks
4. **Grammar Analysis** - Grammatical breakdown (in Japanese)
5. **Use Cases** - Appropriate contexts for the phrase (in Japanese)
6. **Trivia** - Interesting facts about the phrase, cultural context (in Japanese with English translation)
7. **Synonyms** - Alternative expressions with differences (in Japanese)
8. **Structure Analysis** - Detailed explanation of key components (in Japanese)
   - Focus on challenging grammar patterns (e.g., 把字句, 被字句)
   - Explain particle usage and word order
   - Highlight cultural nuances
9. **Character Breakdown** - Individual character analysis for complex characters
10. **Regional Variations** - Differences between mainland China, Taiwan, Hong Kong usage

### For Japanese Input (e.g., "了解しました")

When you input Japanese text, I will provide:

1. **Chinese Translations** - Up to 10 different ways to express it in Chinese (list format)
   - Include formal and informal versions
   - Show both simplified and traditional characters
   - Add regional variations where appropriate
   - Show context-dependent variations
   - Include pinyin for each translation

### Special Commands

- Input: `总结` / `總結` - I will summarize everything covered in our session
- `--traditional` flag - Force traditional character mode
- `--simplified` flag - Force simplified character mode (default)

## Audio Generation

For all Chinese inputs, I will generate audio using the speech synthesis API:
- Endpoint: https://langup-prod.onrender.com/generate-speech/
- **Method: POST request only** (NOT GET - will fail with 405 error)
- **Tool: Use Bash with curl** (NOT WebFetch - WebFetch only does GET requests)
- Language: zh-CN (Mandarin Chinese)
- The audio link will be provided in a clickable format

### Required curl command format:
```bash
curl -X POST https://langup-prod.onrender.com/generate-speech/ \
  -H "Content-Type: application/json" \
  -d '{"text": "word", "lang_code": "zh-CN"}' \
  -s
```

## Anki Field Mapping

### For Words:
- **Front**: The meaning/translation in Japanese (what you see)
- **Back**: The input Chinese word with pinyin (what you need to recall/type)
- **Sound**: The generated audio file URL
- **Example**: Multiple example sentences with Japanese translations
- **Parse**: Pinyin, part of speech, stroke count
- **Use case**: The contexts where it's used
- **In addition**: Character analysis, radicals, trivia information
- **Synonyms**: The synonyms with explanations and alternative forms

### For Sentences/Phrases:
- **Front**: Sound file with pinyin (what you see and hear)
- **Back**: The input Chinese sentence/phrase (what you need to recall/type)
- **Sound**: -
- **Example**: The Japanese translation of the input sentence
- **Parse**: The grammatical structure analysis with pinyin
- **Use case**: The contexts where the phrase is used
- **In addition**: The structural analysis, character breakdown, and cultural trivia
- **Synonyms**: Alternative expressions with differences

## Anki Integration

### AnkiConnect API (Primary Method)

The command will automatically add cards to Anki using AnkiConnect API:

1. **Prerequisites**: 
   - Install AnkiConnect add-on in Anki (code: 2055492159)
   - Ensure Anki is running
   - Default endpoint: http://localhost:8765

2. **Usage**:
   - Basic: `/anki-zh word` - Auto-detects "Chinese" deck
   - Custom deck: `/anki-zh word --deck "Custom Deck"`
   - With model: `/anki-zh word --model "Custom Note Type"`
   - Traditional: `/anki-zh word --traditional`

3. **Auto-detected decks**:
   - Chinese content → "Chinese" deck
   - Can be overridden with --deck flag

4. **Note Type**: Uses "20250705_Basic (解答タイピング入力)" by default, or your custom note type with these fields:
   - Front
   - Back
   - Sound
   - Example
   - Parse
   - Use case
   - In addition
   - Synonyms

### Implementation Steps

When adding a card via AnkiConnect:

1. **Check AnkiConnect availability**: Test connection to http://localhost:8765
2. **Verify/Create deck**: Use `deckNames` to check, `createDeck` if needed
3. **Download audio**: Save the generated audio file locally
4. **Add note**: Use `addNote` with all fields populated
5. **Add media**: Include audio file in the media collection

### API Call Examples

#### For Words:
```bash
curl localhost:8765 -X POST -d '{
  "action": "addNote",
  "params": {
    "note": {
      "deckName": "Chinese",
      "modelName": "20250705_Basic (解答タイピング入力)",
      "fields": {
        "Front": "学ぶ、勉強する / to study, to learn",
        "Back": "学习 (xuéxí)",
        "Sound": "[sound:xuexi.mp3]",
        "Example": "我在学习中文 / 私は中国語を勉強しています\n他很喜欢学习 / 彼は勉強がとても好きです",
        "Parse": "xuéxí, 动词 (Verb), 6+9画",
        "Use case": "教育、自己啓発、スキル習得の文脈で使用",
        "In addition": "学(学ぶ)+习(練習する) / 「學」は繁体字では「學」",
        "Synonyms": "学会 (xuéhuì) - より具体的な習得, 读书 (dúshū) - 本を読んで学ぶ"
      },
      "audio": [{
        "url": "https://lang-up.s3.amazonaws.com/speech/xxx.mp3",
        "filename": "xuexi_timestamp.mp3",
        "fields": ["Sound"]
      }]
    }
  }
}'
```

#### For Sentences/Phrases:
```bash
curl localhost:8765 -X POST -d '{
  "action": "addNote",
  "params": {
    "note": {
      "deckName": "Chinese",
      "modelName": "20250705_Basic (解答タイピング入力)",
      "fields": {
        "Front": "[sound:sentence_timestamp.mp3] wǒ hěn xǐhuān xué zhōngwén",
        "Back": "我很喜欢学中文",
        "Sound": "",
        "Example": "私は中国語を勉強するのがとても好きです",
        "Parse": "我(主語) + 很(副詞) + 喜欢(動詞) + 学(動詞) + 中文(目的語)",
        "Use case": "趣味や学習について話すとき、自己紹介",
        "In addition": "「很」は程度を表す副詞、「中文」は中国語の意味",
        "Synonyms": "我爱学中文 (より強い感情), 我喜欢学汉语 (より正式)"
      },
      "audio": [{
        "url": "https://lang-up.s3.amazonaws.com/speech/xxx.mp3",
        "filename": "sentence_timestamp.mp3",
        "fields": ["Front"]
      }]
    }
  }
}'
```

### Character Support

- **Default**: Simplified Chinese (简体字)
- **Traditional Support**: Use `--traditional` flag
- **Auto-detection**: Recognizes input character type
- **Conversion**: Shows both forms when they differ
- **Regional Notes**: Indicates usage differences (Mainland, Taiwan, Hong Kong)

### Fallback Options

If AnkiConnect is not available:

1. **Tab-Separated Values (TSV)**: Display content for manual copy-paste
2. **CSV Export**: Option to save as .csv file for bulk import
3. **Error Message**: Clear instructions on installing AnkiConnect

### Output Format Example (Fallback)
```
Front[TAB]Back[TAB]Sound[TAB]Example[TAB]Parse[TAB]Use case[TAB]In addition[TAB]Synonyms
学ぶ、勉強する / to study, to learn[TAB]学习 (xuéxí)[TAB]https://langup-bucket.s3.amazonaws.com/speech/xxx.mp3[TAB]我在学习中文 / 私は中国語を勉強しています[TAB]xuéxí, 动词 (Verb), 6+9画[TAB]教育、自己啓発の文脈で使用[TAB]学(学ぶ)+习(練習する)の組み合わせ[TAB]学会 (より具体的), 读书 (本を読んで学ぶ)
```
