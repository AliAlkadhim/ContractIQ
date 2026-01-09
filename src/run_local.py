import os

def main():
    # Avoid GPU weirdness on some setups
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)

if __name__ == "__main__":
    main()
