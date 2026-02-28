import os
import anthropic

api_key = os.environ.get('ANTHROPIC_API_KEY')
if not api_key:
    print('No API key found. Run: setx ANTHROPIC_API_KEY your-key')
    exit(1)

client = anthropic.Anthropic(api_key=api_key)

SYSTEM = 'You are ClawBot, an AI assistant helping build ClawGrab - a video transcript tool for AI power users. Be concise and practical.'

history = []
print()
print('ClawBot ready! Type exit to quit, clear to reset.')
print()

while True:
    try:
        user_input = input('You: ').strip()
    except:
        break
    if not user_input:
        continue
    if user_input.lower() == 'exit':
        break
    if user_input.lower() == 'clear':
        history = []
        print('Chat cleared.')
        continue
    history.append({'role': 'user', 'content': user_input})
    try:
        r = client.messages.create(model='claude-haiku-4-5-20251001', max_tokens=1000, system=SYSTEM, messages=history)
        reply = r.content[0].text
        history.append({'role': 'assistant', 'content': reply})
        print(f'ClawBot: {reply}\n')
    except Exception as e:
        print(f'Error: {e}')
