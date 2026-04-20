# Anki Language Learning Assistant

## Overview
This command helps you learn languages by generating comprehensive explanations and Anki flashcard content for English words, phrases, and sentences. It also supports translation from Japanese to English.

## Usage
```
/anki [word/phrase/sentence]
```

Examples:
- `/anki craving` - Explains the English word "craving"
- `/anki The deal fell through at the last minute` - Explains the English sentence
- `/anki 了解しました` - Provides English translations for the Japanese phrase

## Behavior

### For English Words (e.g., "message", "preview")

When you input an English word, I will provide:

1. **Meaning** - Definition in English followed by Japanese translation
2. **Audio File** - Generated pronunciation link
3. **Part of Speech** - Grammatical category in English
4. **Use Cases** - Common contexts where the word is used (in English)
5. **Trivia** - Interesting facts about the word, if any (in English with Japanese translation)
6. **Synonyms** - Similar words with explanations of differences (in English)
7. **Standard Examples** - 3 example sentences with Japanese translations (displayed as a list)
8. **Slang Examples** - 3 colloquial usage examples with translations (displayed as a list)
9. **Visual Representation** - Mermaid diagram if applicable (in English)

**Console Display**: All example sentences will be shown in the terminal for easy review before adding to Anki.

**Final Response Format**: After adding to Anki, display a clear summary with:
- Success confirmation
- All standard example sentences
- All slang/colloquial examples  
- Quick pronunciation note

### For English Sentences (e.g., "I'm really into it")

When you input an English sentence, I will provide:

1. **Meaning** - Explanation in English followed by Japanese translation
2. **Audio File** - Generated pronunciation link
3. **Part of Speech Analysis** - Grammatical breakdown (in English)
4. **Use Cases** - Appropriate contexts for the phrase (in English)
5. **Trivia** - Interesting facts about the phrase, if any (in English with Japanese translation)
6. **Synonyms** - Alternative expressions with differences (in English)
7. **Structure Analysis** - Detailed explanation of key components (in English)
   - Focus on challenging elements (e.g., "really into" in "I'm really into it")
   - Skip basic words (I'm, it) unless they have special usage
   - Explain why specific prepositions or constructions are used
8. **Additional Trivia** - Extra cultural or linguistic insights (英語と日本語でそれぞれ記載してください)

### For Japanese Input (e.g., "了解しました")

When you input Japanese text, I will provide:

1. **English Translations** - Up to 10 different ways to express it in English (list format)
   - Include formal and informal versions
   - Add phrasal verbs and slang where appropriate
   - Show context-dependent variations


**Caution**: Don't generate sound file if user input is Japanese text

### Special Commands

- Input: `まとめ` - I will summarize everything covered in our session

## Audio Generation

For all English inputs, I will generate audio using the speech synthesis API:
- Endpoint: https://langup-prod.onrender.com/generate-speech/
- **Method: POST request only** (NOT GET - will fail with 405 error)
- **Tool: Use Bash with curl** (NOT WebFetch - WebFetch only does GET requests)
- Language: en-US
- The audio link will be provided in a clickable format

### Required curl command format:
```bash
curl -X POST https://langup-prod.onrender.com/generate-speech/ \
  -H "Content-Type: application/json" \
  -d '{"text": "word", "lang_code": "en-US"}' \
  -s
```

## Anki Field Mapping

### For Words:
- **Front**: The meaning/translation (what you see)
- **Back**: The input word (what you need to recall/type)
- **Sound**: The generated audio file URL
- **Example**: Multiple example sentences with translations
- **Parse**: The part of speech information
- **Use case**: The contexts where it's used
- **In addition**: The trivia information (日本語と英語で記載)
- **Synonyms**: The synonyms with explanations

### For Sentences/Phrases:
- **Front**: Sound file (what you see and hear)
- **Back**: The input sentence/phrase (what you need to recall/type)
- **Sound**: -
- **Example**: The Japanese translation of the input sentence
- **Parse**: The grammatical structure analysis
- **Use case**: The contexts where the phrase is used
- **In addition**: The structural analysis and trivia (日本語と英語で記載)
- **Synonyms**: Alternative expressions with differences

## Anki Integration

### AnkiConnect API (Primary Method)

The command will automatically add cards to Anki using AnkiConnect API:

1. **Prerequisites**: 
   - Install AnkiConnect add-on in Anki (code: 2055492159)
   - Ensure Anki is running
   - Default endpoint: http://localhost:8765

2. **Usage**:
   - Basic: `/anki word` - Auto-detects deck based on language
   - Custom deck: `/anki word --deck "Custom Deck"`
   - With model: `/anki word --model "Custom Note Type"`

3. **Auto-detected decks** based on language:
   - English words/phrases → "English" deck
   - German content → "German" deck
   - Korean content → "Korean" deck
   - Chinese content → "Chinese" deck
   - Thai content → "Thai" deck

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
      "deckName": "English",
      "modelName": "20250705_Basic (解答タイピング入力)",
      "fields": {
        "Front": "To remove liquid; to deplete / 排水する、消耗させる",
        "Back": "drain",
        "Sound": "[sound:drain.mp3]",
        "Example": "Please drain the pasta / パスタの水を切ってください\nThe swamp was drained to create farmland / 沼地は農地を作るために排水された",
        "Parse": "Verb, Noun",
        "Use case": "Removing liquids, depleting resources",
        "In addition": "(日本語と英語で記載)",
        "Synonyms": "empty, deplete, exhaust"
      },
      "audio": [{
        "url": "https://lang-up.s3.amazonaws.com/speech/xxx.mp3",
        "filename": "drain_timestamp.mp3",
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
      "deckName": "English",
      "modelName": "20250705_Basic (解答タイピング入力)",
      "fields": {
        "Front": "[sound:sentence.mp3]",
        "Back": "His poor performance led to a demotion to assistant manager.",
        "Sound": "",
        "Example": "彼の成績不振により、アシスタントマネージャーに降格された。",
        "Parse": "Subject + past verb phrase + prepositional result",
        "Use case": "HR discussions, performance reviews",
        "In addition": "(日本語と英語で記載)",
        "Synonyms": "resulted in, caused, brought about"
      },
      "audio": [{
        "url": "https://lang-up.s3.amazonaws.com/speech/xxx.mp3",
        "filename": "sentence_timestamp.mp3",
        "fields": ["Sound"]
      }]
    }
  }
}'
```

### Fallback Options

If AnkiConnect is not available:

1. **Tab-Separated Values (TSV)**: Display content for manual copy-paste
2. **CSV Export**: Option to save as .csv file for bulk import
3. **Error Message**: Clear instructions on installing AnkiConnect

### Output Format Example (Fallback)
```
Front[TAB]Back[TAB]Sound[TAB]Example[TAB]Parse[TAB]Use case[TAB]In addition[TAB]Synonyms
A strong desire for something / 強い欲求[TAB]craving[TAB]https://langup-bucket.s3.amazonaws.com/speech/xxx.mp3[TAB]I have a craving for chocolate / チョコレートが食べたくてたまらない[TAB]Noun[TAB]When expressing strong desires for food, experiences, or habits[TAB]Often associated with pregnancy or addiction contexts[TAB]desire (milder), yearning (more poetic), hankering (informal)
```
