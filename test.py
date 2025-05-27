import base64


def image_to_base64(image_path):
    try:
        with open(image_path, "rb") as image_file:
            # Read the image file in binary mode
            image_data = image_file.read()
            # Convert to base64
            base64_string = base64.b64encode(image_data).decode("utf-8")
            return base64_string
    except FileNotFoundError:
        return "Error: Image file not found"
    except Exception as e:
        return f"Error: {str(e)}"


# Example usage
if __name__ == "__main__":
    image_path = r"C:\Users\George Elkomos\Desktop\Book1.pdf"  # Replace with your image path
    result = image_to_base64(image_path)
    print(result)
