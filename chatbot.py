from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

template="""
Answer the Question Below.

Here is the conversation history:{context}

Questions:{question}

Answer:
"""

model=OllamaLLM(model="llama3")
prompt=ChatPromptTemplate.from_template(template)
chain=prompt|model

def handle_conversation():
    context=""
    print("Welcome to AI Chatbot!Type 'exit' to quit.")
    while True:
        user_input=input("You:")
        
        if user_input.lower()=='exit':
            break
        
        result=chain.invoke({"context":"","question":user_input})
        print("BOT:",result)
        context+=f"\nUser:{user_input}\nAI:{result}"

if __name__=="__main__":
    handle_conversation()