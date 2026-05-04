# Anki Russian Language Learning Assistant

## Overview
This command helps you learn Russian by generating comprehensive explanations and Anki flashcard content for Russian words, phrases, and sentences. It also supports translation from Japanese/English to Russian.

## Usage
```
/anki-ru [word/phrase/sentence]
```

Examples:
- `/anki-ru привет` - Explains the Russian word "привет" (hello)
- `/anki-ru Как дела?` - Explains the Russian phrase "How are you?"
- `/anki-ru hello` - Provides Russian translations for the English word
- `/anki-ru こんにちは` - Provides Russian translations for the Japanese word

## Behavior

### For Russian Words (e.g., "книга", "работать")

When you input a Russian word, I will provide:

1. **Meaning** - Definition in English followed by Japanese translation
2. **Audio File** - Generated pronunciation link
3. **Part of Speech** - Grammatical category in English
4. **Declension/Conjugation** - Case forms for nouns or verb conjugations
5. **Use Cases** - Common contexts where the word is used (in English)
6. **Trivia** - Interesting facts about the word, if any (in English with Japanese translation)
7. **Synonyms** - Similar words with explanations of differences (in English)
8. **Standard Examples** - 3 example sentences with English/Japanese translations (displayed as a list)
9. **Colloquial Examples** - 3 everyday usage examples with translations (displayed as a list)
10. **Visual Representation** - Mermaid diagram if applicable (in English)

**Console Display**: All example sentences will be shown in the terminal for easy review before adding to Anki.

**Final Response Format**: After adding to Anki, display a clear summary with:
- Success confirmation
- All standard example sentences
- All colloquial examples  
- Quick pronunciation note

### For Russian Sentences (e.g., "Я изучаю русский язык")

When you input a Russian sentence, I will provide:

1. **Meaning** - Explanation in English followed by Japanese translation
2. **Audio File** - Generated pronunciation link
3. **Part of Speech Analysis** - Grammatical breakdown (in English)
4. **Case Analysis** - Explanation of cases used in the sentence
5. **Use Cases** - Appropriate contexts for the phrase (in English)
6. **Trivia** - Interesting facts about the phrase, if any (in English with Japanese translation)
7. **Synonyms** - Alternative expressions with differences (in English)
8. **Structure Analysis** - Detailed explanation of key components (in English)
   - Focus on case usage and verb aspects
   - Explain word order and its flexibility
   - Highlight cultural nuances
9. **Additional Trivia** - Extra cultural or linguistic insights (in English with Japanese translation)

### For English/Japanese Input

When you input English or Japanese text, I will provide:

1. **Russian Translations** - Up to 10 different ways to express it in Russian (list format)
   - Include formal and informal versions (ты/вы forms)
   - Add colloquial and slang expressions where appropriate
   - Show context-dependent variations
   - Include relevant case forms

### Special Commands

- Input: `итог` - I will summarize everything covered in our session

## Audio Generation

For all Russian inputs, I will generate audio using the speech synthesis API:
- Endpoint: http://localhost:10000/generate-speech/
- **Method: POST request only** (NOT GET - will fail with 405 error)
- **Tool: Use Bash with curl** (NOT WebFetch - WebFetch only does GET requests)
- Language: ru-RU
- The audio link will be provided in a clickable format

### Required curl command format:
```bash
curl -X POST http://localhost:10000/generate-speech/ \
  -H "Content-Type: application/json" \
  -d '{"text": "слово", "lang_code": "ru-RU"}' \
  -s
```

## Anki Field Mapping

### For Words:
- **Front**: The meaning/translation (what you see)
- **Back**: The input word (what you need to recall/type)
- **Sound**: The generated audio file URL
- **Example**: Multiple example sentences with translations
- **Parse**: The part of speech and declension/conjugation info
- **Use case**: The contexts where it's used
- **In addition**: The trivia information
- **Synonyms**: The synonyms with explanations

### For Sentences/Phrases:
- **Front**: Sound file (what you see and hear)
- **Back**: The input sentence/phrase (what you need to recall/type)
- **Sound**: -
- **Example**: The English/Japanese translation of the input sentence
- **Parse**: The grammatical structure and case analysis
- **Use case**: The contexts where the phrase is used
- **In addition**: The structural analysis and trivia
- **Synonyms**: Alternative expressions with differences

## Anki Integration

### AnkiConnect API (Primary Method)

The command will automatically add cards to Anki using AnkiConnect API:

1. **Prerequisites**: 
   - Install AnkiConnect add-on in Anki (code: 2055492159)
   - Ensure Anki is running
   - Default endpoint: http://localhost:8765

2. **Usage**:
   - Basic: `/anki-ru слово` - Auto-adds to "Russian" deck
   - Custom deck: `/anki-ru слово --deck "Custom Deck"`
   - With model: `/anki-ru слово --model "Custom Note Type"`

3. **Default deck**: "Russian"

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
      "deckName": "Russian",
      "modelName": "20250705_Basic (解答タイピング入力)",
      "fields": {
        "Front": "Book / 本",
        "Back": "книга",
        "Sound": "[sound:kniga.mp3]",
        "Example": "Я читаю книгу / I am reading a book / 私は本を読んでいます\nЭто интересная книга / This is an interesting book / これは面白い本です",
        "Parse": "Noun, feminine. Nom: книга, Gen: книги, Dat: книге, Acc: книгу, Inst: книгой, Prep: о книге",
        "Use case": "Reading materials, literature, educational contexts",
        "In addition": "From Old Church Slavonic кънига, originally from Chinese",
        "Synonyms": "том (volume, more formal), издание (edition), произведение (work)"
      },
      "audio": [{
        "url": "https://lang-up.s3.amazonaws.com/speech/xxx.mp3",
        "filename": "kniga_timestamp.mp3",
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
      "deckName": "Russian",
      "modelName": "20250705_Basic (解答タイピング入力)",
      "fields": {
        "Front": "[sound:sentence.mp3]",
        "Back": "Я изучаю русский язык",
        "Sound": "",
        "Example": "I am studying Russian language / 私はロシア語を勉強しています",
        "Parse": "Я (nom) изучаю (1st person, imperfective) русский (acc, adj) язык (acc, noun)",
        "Use case": "Self-introduction, language learning contexts",
        "In addition": "изучать implies deep, systematic study vs учить (general learning)",
        "Synonyms": "Я учу русский язык (more casual), Я занимаюсь русским языком (engaged with)"
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
Hello / こんにちは[TAB]привет[TAB]https://langup-bucket.s3.amazonaws.com/speech/xxx.mp3[TAB]Привет! Как дела? / Hello! How are you? / こんにちは！元気ですか？[TAB]Interjection, informal greeting[TAB]Casual greetings between friends, informal situations[TAB]From приветствие (greeting), related to приветливый (friendly)[TAB]здравствуй (slightly more formal), здравствуйте (formal/plural), добрый день (good day)
```
