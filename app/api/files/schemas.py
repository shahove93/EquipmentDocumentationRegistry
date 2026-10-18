from datetime import datetime

from pydantic import BaseModel, ConfigDict, RootModel


class FileOut(BaseModel):
    """Response body representing a stored attachment.

    `from_attributes` lets the schema serialise an ORM `File` row directly, the
    same way `DocumentOut` and `IssuerRead` do.

    `storage_key` is deliberately absent. It is the internal path of the blob
    under the storage root: the client never needs it, and publishing it would
    expose the layout of the filesystem. Spelling the fields out — rather than
    deriving the schema from the model — is what keeps it out of the JSON body
    and out of the generated OpenAPI document.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime


class FileListOut(RootModel[list[FileOut]]):
    """Response body for a collection of attachments.

    A bare JSON array, matching `DocumentListOut` and every existing collection
    endpoint in the project: the page is returned directly and carries no total,
    so paging stays the caller's concern. ADR-009 fixes the same shape for the
    list of a document's files.
    """
