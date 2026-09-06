import os
import time
from pathlib import Path

from dotenv import load_dotenv
from tqdm.auto import tqdm
from pinecone import Pinecone, ServerlessSpec

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings


load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

PINECONE_ENV = "us-east-1"
PINECONE_INDEX_NAME = "medicalindex"

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

UPLOAD_DIR = "./uploaded_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# -----------------------------
# Initialize Pinecone
# -----------------------------

pc = Pinecone(api_key=PINECONE_API_KEY)

spec = ServerlessSpec(
    cloud="aws",
    region=PINECONE_ENV
)

existing_indexes = [i["name"] for i in pc.list_indexes()]

if PINECONE_INDEX_NAME not in existing_indexes:
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=768,
        metric="dotproduct",
        spec=spec
    )

    while not pc.describe_index(PINECONE_INDEX_NAME).status["ready"]:
        time.sleep(1)


index = pc.Index(PINECONE_INDEX_NAME)


# -----------------------------
# Load, split, embed and upload
# -----------------------------

def load_vectorstore(uploaded_files):

    embed_model = GoogleGenerativeAIEmbeddings(  
        model="models/gemini-embedding-001",
        output_dimensionality=768
    )

    file_paths = []

    # Save uploaded files
    for file in uploaded_files:

        save_path = Path(UPLOAD_DIR) / file.filename

        with open(save_path, "wb") as f:
            f.write(file.file.read())

        file_paths.append(str(save_path))

        print(f"📄 Saved: {save_path}")


    # Process every PDF
    for file_path in file_paths:

        print(f"\n📖 Processing: {file_path}")

        # Load PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        print(f"📑 Pages loaded: {len(documents)}")

        if not documents:
            raise ValueError(
                f"No pages could be extracted from PDF: {file_path}"
            )


        # Split documents
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )

        chunks = splitter.split_documents(documents)

        print(f"🧩 Chunks created: {len(chunks)}")

        if not chunks:
            raise ValueError(
                f"No text chunks were created from PDF: {file_path}"
            )


        # Extract text
        texts = [
            chunk.page_content.strip()
            for chunk in chunks
            if chunk.page_content and chunk.page_content.strip()
        ]

        # Metadata
        # Metadata
        metadatas = [
         {
        **chunk.metadata,
        "text": chunk.page_content.strip()
           }
          for chunk in chunks
            if chunk.page_content and chunk.page_content.strip()
           ]

        print(f"📝 Non-empty chunks: {len(texts)}")

        if not texts:
            raise ValueError(
                f"PDF contains no extractable text: {file_path}"
            )


        # IDs
        ids = [
            f"{Path(file_path).stem}-{i}"
            for i in range(len(texts))
        ]


        # Generate embeddings
        print(f"🔍 Embedding {len(texts)} chunks...")

        embeddings = embed_model.embed_documents(texts)

        print(f"✅ Embeddings generated: {len(embeddings)}")


        if len(embeddings) != len(texts):
            raise ValueError(
                "Number of embeddings does not match number of text chunks."
            )


        # Pinecone upload
        print("📤 Uploading to Pinecone...")

        vectors = list(
            zip(
                ids,
                embeddings,
                metadatas
            )
        )

        if not vectors:
            raise ValueError(
                "No vectors were generated. Nothing to upload to Pinecone."
            )


        with tqdm(
            total=len(vectors),
            desc="Upserting to Pinecone"
        ) as progress:

            index.upsert(vectors=vectors)

            progress.update(len(vectors))


        print(f"✅ Upload complete for {file_path}")