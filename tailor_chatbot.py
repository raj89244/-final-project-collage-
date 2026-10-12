# Simple Tailor Website Chatbot
# Save this file as tailor_chatbot.py and run with: python tailor_chatbot.py

responses = {
    "hello": "Hello! Welcome to TailorBot. How can I help you with your tailoring query today?",
    "hi": "Hi there! I can answer questions about measurements, orders, delivery and tailor services.",
    "order": "If you want to place an order, share your measurement details and the garment type.",
    "measurement": "For measurements, please give chest, waist, hip, shoulder and length details.",
    "delivery": "Delivery usually takes 3-5 business days after the stitching is complete.",
    "price": "The price depends on fabric, design and work. Please tell me what garment you need.",
    "fabric": "We offer cotton, silk, linen, and blended fabrics. Tell me which one you prefer.",
    "alteration": "Alterations are available. Share the garment type and the fit changes you need.",
    "contact": "You can contact our tailor support by email or phone from the Contact Us page.",
    "thank": "You are welcome! If you have more questions, I am here to help.",
    "bye": "Goodbye! Thanks for visiting our tailor service. Have a great day!"
}

fallback = "I am not sure I understood. Please ask about orders, measurements, delivery, fabric, pricing, or alterations."


def get_response(message: str) -> str:
    message = message.lower().strip()
    for key, answer in responses.items():
        if key in message:
            return answer
    return fallback


def main() -> None:
    print("Welcome to TailorBot! Ask your question about the tailor website.")
    print("Type 'exit' or 'bye' to quit.")
    try:
        while True:
            user_input = input("You: ")
            if not user_input:
                print("TailorBot: Please type your question.")
                continue

            if user_input.lower().strip() in ["exit", "quit", "bye"]:
                print("TailorBot: Goodbye! If you need more help, visit our tailor website again.")
                break

            answer = get_response(user_input)
            print(f"TailorBot: {answer}")
    except KeyboardInterrupt:
        print("\nTailorBot: Goodbye! Thanks for using TailorBot.")


if __name__ == "__main__":
    main()
