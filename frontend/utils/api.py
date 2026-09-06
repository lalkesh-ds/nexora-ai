# import requests
# from config import API_URL


# def upload_pdfs_api(files):
#     files_payload=[ ("files",(f.name,f.read(),"application/pdf")) for f in files]
#     return requests.post(f"{API_URL}/upload_pdfs/",files=files_payload)

# def ask_question(question):
#     return requests.post(f"{API_URL}/ask/",data={"question":question})

import requests

from config import API_URL


def upload_pdfs_api(files):

    files_payload = [
        ("files", (f.name, f.read(), "application/pdf"))
        for f in files
    ]

    url = f"{API_URL}/upload_pdfs/"

    print("UPLOAD URL:", url)

    return requests.post(
        url,
        files=files_payload
    )


def ask_question(question):

    url = f"{API_URL}/ask/"

    print("ASK URL:", url)

    return requests.post(
        url,
        data={"question": question}
    )