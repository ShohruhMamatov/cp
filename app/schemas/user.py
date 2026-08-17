from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=50)
    email: EmailStr | None = None
    # 72 is not arbitrary: bcrypt silently truncates past 72 bytes, so a longer
    # password would validate against its own first 72 characters.
    password: str = Field(min_length=8, max_length=72)
    password_repeat: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_repeat:
            raise ValueError("passwords do not match")
        return self


class UserLogin(BaseModel):
    login: str
    password: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)
    new_password_repeat: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.new_password_repeat:
            raise ValueError("passwords do not match")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    email: EmailStr | None = None
